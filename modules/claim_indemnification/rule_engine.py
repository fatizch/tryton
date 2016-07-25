# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.rule_engine import check_args

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngine',
    'RuleEngineRuntime',
    ]


class RuleEngine:
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection.extend([
            ('benefit', 'Benefit'),
            ('benefit_deductible', 'Benefit: Deductible')])

    def on_change_with_result_type(self, name=None):
        if self.type_ == 'benefit':
            return 'list'
        elif self.type_ == 'benefit_deductible':
            return 'date'
        return super(RuleEngine, self).on_change_with_result_type(name)


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('start_date')
    def _re_indemnification_start_date(cls, args):
        return args['start_date']

    @classmethod
    @check_args('end_date')
    def _re_indemnification_end_date(cls, args):
        return args['end_date']

    @classmethod
    @check_args('benefit', 'option')
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
                ])
        res = 0
        for detail in details:
            res += (min(to_date, detail.end_date) -
                max(from_date, detail.start_date)).days + 1
        return res

    @classmethod
    @check_args('indemnification', 'start_date', 'end_date')
    def _re_detail_period_start_date(cls, args):
        res = []
        for service in args['indemnification'].service.loss.services:
            if service == args['indemnification'].service:
                continue
            for indemn in service.indemnifications:
                for detail in indemn.details:
                    if detail.start_date > args['start_date'] and \
                            detail.start_date < args['end_date']:
                        res.append(detail.start_date)
        res.sort()
        return res

    @classmethod
    @check_args('indemnification')
    def _re_sum_of_unit_amount(cls, args, date):
        res = 0
        for service in args['indemnification'].service.loss.services:
            if service == args['indemnification'].service:
                continue
            for indemn in service.indemnifications:
                for detail in indemn.details:
                    if detail.start_date <= date and detail.end_date >= date:
                        res += detail.amount_per_unit
        return res

    @classmethod
    @check_args('service')
    def _re_service_period_frequency(cls, args):
        return args['service'].period_frequency

    @classmethod
    @check_args('indemnification')
    def _re_amount(cls, args):
        return args['indemnification'].amount

    @classmethod
    @check_args('service')
    def _re_deductible_end_date(cls, args):
        return args['service'].deductible_end_date
