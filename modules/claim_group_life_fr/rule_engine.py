# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.pool import PoolMeta, Pool

from trytond.modules.rule_engine import check_args
from trytond.modules.coog_core import coog_date


__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime(metaclass=PoolMeta):
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('loss')
    def _re_total_hospitalisation_period(cls, args):
        return sum([coog_date.number_of_days_between(
                    x.start_date, x.end_date)
                for x in args['loss'].hospitalisation_periods])

    @classmethod
    @check_args('indemnification', 'indemnification_detail_start_date')
    def _re_ijss_before_part_time(cls, args):
        delivered = args['indemnification'].service
        at_date = args['indemnification_detail_start_date']
        ijss = {e.date or delivered.loss.start_date:
            e.extra_data_values['ijss']
            if 'ijss' in e.extra_data_values else 0
            for e in delivered.extra_datas
            if (e.date or delivered.loss.start_date) < at_date}
        dates = sorted(list(ijss.keys()), reverse=True)
        part_times = [x for x in delivered.loss.deduction_periods
            if x.deduction_kind.code == 'part_time' and x.start_date
            and x.start_date < at_date]

        def part_time_period_at_date(date):
            for part_time in part_times:
                if part_time.start_date <= date and part_time.end_date >= date:
                    return part_time

        for date in dates:
            if not part_time_period_at_date(date):
                return ijss[date]
        return Decimal('0')

    @classmethod
    def _re_ltd_periods(cls, args, periods, description, annuity_amount,
            ss_annuity_amount, reference_salary, net_reference_salary,
            trancheTA, trancheTB, trancheTC, rounding_factor=None,
            annex_rule_code=None):
        '''
            This method computes annuity periods given an initial annuity
            amount, social security amount to deduce, salary values and
            a rule to deduce annex benefits
            This method's periods parameter is an annuity periods list.
            Such a list containts tuples with:
                * start_date
                * end_date
                * full_period to know if the period is a full period
                * prorata which represents the period's months number if it is
                  a full period and the period's days number otherwise
                * unit which represents the time unit, 'days', 'months', ...
            The method returns a list of such periods after deduction and
            with additional information about base amount, amount per unit...
        '''
        if not rounding_factor:
            rounding_factor = Decimal('0.01')
        annex_rules = None
        if annex_rule_code:
            RuleEngine = Pool().get('rule_engine')
            annex_rules = RuleEngine.search(
                [('short_name', '=', annex_rule_code)])
            if not annex_rules:
                raise Exception('No rule found for code %s' % annex_rule_code)
        res = []
        description_copy = description
        for start_date, end_date, full_period, prorata, unit in periods:
            description = description_copy
            ratio = 365
            if full_period:
                ratio = 12
            rounded_annuity_amount = cls._re_round(args, annuity_amount,
                rounding_factor)
            rounded_reference_salary = cls._re_round(args, reference_salary,
                rounding_factor)
            rounded_net_reference_salary = cls._re_round(args,
                net_reference_salary, rounding_factor)
            period_ss_annuity = cls._re_round(args,
                ss_annuity_amount / ratio * prorata, rounding_factor)
            if rounded_annuity_amount < 0:
                rounded_annuity_amount = Decimal('0.0')
            if annex_rules:
                annex_rule = annex_rules[0]
                annex_rule_args = {
                    'type_de_regle': annex_rule_code,
                    'date_debut_periode': start_date,
                    'date_fin_periode': end_date,
                    'rente_de_base': rounded_annuity_amount,
                    'salaire_de_reference': rounded_reference_salary,
                    'rente_ss': period_ss_annuity,
                    'salaire_de_reference_net': rounded_net_reference_salary
                    }
                rule_res = annex_rule.execute(
                    arguments=args, parameters=annex_rule_args)
                if rule_res.result:
                    rounded_annuity_amount, annex_description = rule_res.result
                    description += annex_description
            unit_annuity = cls._re_round(args, rounded_annuity_amount / prorata,
                rounding_factor)
            res.append({
                    'start_date': start_date,
                    'end_date': end_date,
                    'nb_of_unit': prorata,
                    'unit': unit,
                    'amount': rounded_annuity_amount,
                    'base_amount': unit_annuity,
                    'amount_per_unit': unit_annuity,
                    'description': description,
                    'extra_details': {
                        'tranche_a': trancheTA,
                        'tranche_b': trancheTB,
                        'tranche_c': trancheTC
                    }
                    })
        return res
