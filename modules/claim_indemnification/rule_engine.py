# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import datetime
from dateutil import rrule
from decimal import Decimal

from sql.aggregate import Count

from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.modules.rule_engine import check_args
from trytond.modules.coog_core import coog_date, fields

__all__ = [
    'RuleEngine',
    'RuleEngineRuntime',
    ]


class RuleEngine(metaclass=PoolMeta):
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection.extend([
                ('benefit', 'Benefit'),
                ('benefit_deductible', 'Benefit: Deductible'),
                ('benefit_revaluation', 'Benefit: Revaluation'),
                ])

    @fields.depends('type_')
    def on_change_with_result_type(self, name=None):
        if self.type_ == 'benefit':
            return 'list'
        elif self.type_ == 'benefit_deductible':
            return 'date'
        return super(RuleEngine, self).on_change_with_result_type(name)


class RuleEngineRuntime(metaclass=PoolMeta):
    __name__ = 'rule_engine.runtime'

    @classmethod
    def _re_indemnification_period_start_date(cls, args):
        if 'indemnification_detail_start_date' in args:
            return args['indemnification_detail_start_date']
        elif 'indemnification' in args:
            return args['indemnification'].start_date

    @classmethod
    def _re_indemnification_period_end_date(cls, args):
        if 'indemnification_detail_end_date' in args:
            return args['indemnification_detail_end_date']
        elif 'indemnification' in args:
            return args['indemnification'].end_date

    @classmethod
    @check_args('indemnification')
    def _re_indemnification_share(cls, args):
        share = args['indemnification'].share
        return share if share is not None else 1

    @classmethod
    @check_args('loss', 'service')
    def _re_total_amount_period_for_covered(cls, args, start=None, end=None,
            kind='capital', for_this_claim=False, ignore_service=False):
        Indemnification = Pool().get('claim.indemnification')
        loss = args.get('loss')
        covered = loss.covered_person
        claim = loss.claim if for_this_claim else None
        service = args.get('service')
        kwargs = {}
        if ignore_service:
            kwargs['services_to_ignore'] = [service]

        def total_amount_for(covered, claim, start, end):
            indemnifications = Indemnification._get_indemnifications_for_period(
                service.option, covered, [kind], start, end, claim, **kwargs)
            return sum(x.total_amount for x in indemnifications)

        return total_amount_for(covered, claim, start=start, end=end)

    @classmethod
    @check_args('loss', 'service')
    def _re_total_indemnification_days_for_covered(cls, args, start=None,
            end=None, kind='period', for_this_claim=None,
            ignore_service=False):
        Indemnification = Pool().get('claim.indemnification')
        loss = args.get('loss')
        covered = loss.covered_person
        claim = loss.claim if for_this_claim else None
        service = args.get('service')
        kwargs = {}
        if ignore_service:
            kwargs['services_to_ignore'] = [service]

        indemnifications = Indemnification._get_indemnifications_for_period(
            service.option, covered, [kind], start, end, claim, **kwargs)

        return sum(coog_date.number_of_days_between(x.start_date, x.end_date)
            for x in indemnifications)

    @classmethod
    @check_args('benefit', 'option', 'loss')
    def _re_number_of_deductible_days(cls, args, from_date, to_date):
        pool = Pool()
        Details = pool.get('claim.indemnification.detail')
        details = Details.search([
                ('kind', '=', 'deductible'),
                ['OR', [
                        ('start_date', '>=', from_date),
                        ('start_date', '<=', to_date)
                        ], [
                        ('end_date', '>=', from_date),
                        ('end_date', '<=', to_date),
                ]],
                ('indemnification.service.benefit', '=', args['benefit'].id),
                ('indemnification.service.option', '=', args['option'].id),
                ('indemnification.service.loss.covered_person', '=',
                    args['loss'].covered_person.id),
                ])
        res = 0
        for detail in details:
            res += (min(to_date, detail.end_date) -
                max(from_date, detail.start_date)).days + 1
        return res

    @classmethod
    @check_args('service')
    def _re_sum_of_unit_amount(cls, args, date):
        res = 0
        for service in args['service'].loss.services:
            if service == args['service']:
                continue
            for indemn in service.indemnifications:
                for detail in indemn.details:
                    if detail.start_date <= date and detail.end_date >= date:
                        res += detail.amount_per_unit
        return res

    @classmethod
    @check_args('service')
    def _re_service_period_frequency(cls, args):
        return args['service'].annuity_frequency

    @classmethod
    @check_args('indemnification')
    def _re_amount(cls, args):
        return args['indemnification'].amount

    @classmethod
    @check_args('service')
    def _re_deductible_end_date(cls, args):
        return args['service'].get_deductible_end_date(args=copy.copy(args))

    @classmethod
    @check_args('service')
    def _re_is_service_deductible(cls, args):
        return args['service'].is_deductible()

    @classmethod
    @check_args('option')
    def _re_count_valid_indemnifications(cls, args):
        pool = Pool()
        cursor = Transaction().connection.cursor()

        service = pool.get('claim.service').__table__()
        indemnification = pool.get('claim.indemnification').__table__()
        option = args['option']

        join_table = indemnification.join(service, condition=(
                (indemnification.service == service.id)
                ))
        cursor.execute(
            *join_table.select(
                Count(indemnification.id), where=(
                    (service.option == option.id) &
                    (indemnification.status.in_(['validated', 'paid']))
                    )))
        result, = cursor.fetchone()
        return int(result)

    @classmethod
    def _re_revaluation_pivot_dates(cls, args, start_date, end_date, frequency,
            month_sync=0, day_sync=0):
        assert frequency in ('YEARLY', 'MONTHLY', 'WEEKLY', 'DAILY')
        start_date = start_date.replace(
            month=month_sync if month_sync else start_date.month,
            day=day_sync if day_sync else start_date.day)
        dates = list(rrule.rrule(getattr(rrule, frequency), dtstart=start_date,
                until=end_date))
        dates.sort()
        return [x.date() for x in dates]

    @classmethod
    def _re_revaluation_sub_periods(cls, args, dates, period_start_date,
            period_end_date):
        if period_start_date is None:
            cls.append_functional_error(
                ValidationError(gettext(
                        'claim_indemnification.msg_wrong_parameters')))
        return coog_date.calculate_periods_from_dates(dates, period_start_date,
            period_end_date)

    @classmethod
    @check_args('description')
    def _re_get_base_salary_calculation_description(cls, args):
        return args['description']

    @classmethod
    @check_args('base_amount')
    def _re_get_daily_base_salary(cls, args):
        return args['base_amount']

    @classmethod
    @check_args('indemnification')
    def _re_maximum_daily_amount_for_indemnification(cls, args):
        amounts = []
        for detail in args['indemnification'].details:
            if not detail.start_date or not detail.end_date:
                continue
            days = (detail.end_date - detail.start_date).days + 1
            amounts.append(detail.amount / days)
        return max(amounts) or Decimal(0)

    @classmethod
    @check_args('indemnification_periods')
    def _re_get_indemnification_periods(cls, args):
        return args['indemnification_periods']

    @classmethod
    @check_args('service')
    def _re_annuity_periods(cls, args, start_date, end_date):
        return args['service'].calculate_annuity_periods(start_date,
            end_date)

    @classmethod
    @check_args('indemnification')
    def _re_indemnification_is_manual(cls, args):
        return args['indemnification'].manual

    @classmethod
    @check_args('indemnification', 'service')
    def _re_beneficiary_documents_reception_date(cls, args):
        beneficiary, = [x for x in args['service'].beneficiaries
            if x.party == args['indemnification'].beneficiary]
        return beneficiary.documents_reception_date

    @classmethod
    @check_args('service')
    def _re_benefit_covered_indemnificated_amount_term(cls, args):
        service = args.get('service')
        return service._get_benefits_covered_indemnificated_amount(
            service.contract.start_date or datetime.date.min,
            service.contract.end_date or datetime.date.max)
