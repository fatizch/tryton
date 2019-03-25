# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.rule_engine import check_args
from trytond.modules.coog_core import coog_date


__all__ = [
    'RuleEngine',
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
    @check_args('indemnification', 'indemnification_detail_start_date',
        'service')
    def _re_ijss_before_part_time(cls, args):
        delivered = args['service']
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
            ss_annuity_amount, reference_salary, trancheTA, trancheTB,
            trancheTC, rounding_factor=None, annex_rule_code=None):
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
        full_start_date = args.get('indemnification_full_start', periods[0][0])
        full_end_date = args.get('indemnification_full_end', periods[-1][1])
        ratio = coog_date.number_of_days_between(full_start_date,
            full_end_date)
        for start_date, end_date, full_period, prorata, unit in periods:
            description = description_copy

            # SS annuity is defined on full period, we must prorate using
            # days as factor
            ratio_sub_period = coog_date.number_of_days_between(start_date,
                end_date)
            period_ss_annuity = cls._re_round(args,
                ss_annuity_amount / ratio * ratio_sub_period,
                rounding_factor)
            description += 'Rente SS sur la sous période: ' \
                '%s (%s / %s * %s)\n' \
                % (period_ss_annuity, ss_annuity_amount, ratio,
                    ratio_sub_period)

            # Round amounts
            rounded_annuity_amount = cls._re_round(args, annuity_amount,
                rounding_factor)
            rounded_reference_salary = cls._re_round(args, reference_salary,
                rounding_factor)

            if rounded_annuity_amount < 0:
                rounded_annuity_amount = Decimal('0.0')

            # Prorate annuity amounts on sub periods
            if full_period:
                unit_annuity = cls._re_round(args, rounded_annuity_amount /
                    Decimal('12') * prorata, rounding_factor)
                description += 'Montant de l\'unité: %s (%s / %s * %s)\n' \
                    % (unit_annuity, rounded_annuity_amount, 12,
                        prorata)
                unit_reference_salary = cls._re_round(args,
                    rounded_reference_salary / Decimal('12') * prorata,
                    rounding_factor)
            else:
                unit_annuity = cls._re_round(args, rounded_annuity_amount /
                   Decimal('365') * ratio_sub_period, rounding_factor)
                description += 'Montant de l\'unité: %s (%s / 365 * %s)\n' % (
                    unit_annuity, rounded_annuity_amount, prorata)
                unit_reference_salary = cls._re_round(args,
                    rounded_reference_salary / Decimal('365') *
                    ratio_sub_period, rounding_factor)

            # Call limitations rules with prorated amounts
            if annex_rules:
                annex_rule = annex_rules[0]
                annex_rule_args = {
                    'type_de_regle': annex_rule_code,
                    'date_debut_periode': start_date,
                    'date_fin_periode': end_date,
                    'rente_de_base': unit_annuity,
                    'salaire_de_reference': unit_reference_salary,
                    'rente_ss': period_ss_annuity,
                    }
                rule_res = annex_rule.execute(
                    arguments=args, parameters=annex_rule_args)
                if rule_res.result:
                    rounded_unit_annuity, annex_description = rule_res.result
                    description += annex_description

            if not full_period:
                unit_annuity = (Decimal(rounded_unit_annuity) /
                    Decimal(ratio_sub_period))
            else:
                unit_annuity = rounded_unit_annuity

            res.append({
                    'start_date': start_date,
                    'end_date': end_date,
                    'nb_of_unit': prorata if not full_period else 1,
                    'unit': unit,
                    'amount': rounded_unit_annuity,
                    'base_amount': unit_annuity,
                    'amount_per_unit': unit_annuity,
                    'description': description,
                    'extra_details': {
                        'tranche_a': trancheTA,
                        'tranche_b': trancheTB,
                        'tranche_c': trancheTC,
                        'rente_ss': period_ss_annuity,
                        }
                    })
        return res


class RuleEngine(metaclass=PoolMeta):
    __name__ = 'rule_engine'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        pool = Pool()
        model_data = pool.get('ir.model.data').__table__()
        table = pool.get('rule_engine-rule_engine').__table__()
        # Migration from 2.2: Removing default rules
        query = model_data.select(model_data.id, model_data.db_id,
            where=model_data.fs_id.in_(
                ['deduire_pole_emploi', 'deduire_mtt']))
        cursor.execute(*query)
        set_ids = [(id_, db_id) for id_, db_id in cursor.fetchall()]
        if set_ids:
            ids = [x for _, x in set_ids]
            data_ids = [x for x, _ in set_ids]
            sub_select = table.select(
                table.id,
                where=table.rule.in_(ids))
            cursor.execute(*table.select(table.parent_rule,
                    where=table.id.in_(sub_select)))
            cursor.execute(*table.delete(
                    where=table.id.in_(sub_select)))
            cursor.execute(*model_data.delete(
                where=model_data.id.in_(data_ids)))
        super(RuleEngine, cls).__register__(module_name)
