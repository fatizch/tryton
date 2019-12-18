# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutils import relativedelta

from trytond.pool import PoolMeta
from trytond.model import Unique

from trytond.modules.coog_core import fields, model, coog_string


__all__ = [
    'LossDescription',
    'DeductionPeriodKind',
    'LossDescriptionDeductionPeriodKindRelation',
    'BenefitRule',
    ]


class LossDescription(metaclass=PoolMeta):
    __name__ = 'benefit.loss.description'

    deduction_period_kinds = fields.Many2Many(
        'benefit.loss.description-deduction_period_kind', 'loss_desc',
        'deduction_period_kind', 'Deduction Period Kinds')


class DeductionPeriodKind(model.CoogSQL, model.CoogView):
    'Deduction Period Kind'

    __name__ = 'benefit.loss.description.deduction_period_kind'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)

    @classmethod
    def __setup__(cls):
        super(DeductionPeriodKind, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_unique', Unique(t, t.code), 'The code must be unique'),
            ]
        cls._order = [('code', 'ASC')]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)


class LossDescriptionDeductionPeriodKindRelation(model.CoogSQL):
    'Loss Description to Deduction Period Kind Relation'

    __name__ = 'benefit.loss.description-deduction_period_kind'

    loss_desc = fields.Many2One('benefit.loss.description', 'Loss Description',
        required=True, select=True, ondelete='CASCADE')
    deduction_period_kind = fields.Many2One(
        'benefit.loss.description.deduction_period_kind',
        'Deduction Period Kind', required=True, select=True,
        ondelete='RESTRICT')


class BenefitRule(metaclass=PoolMeta):
    __name__ = 'benefit.rule'

    @classmethod
    def _add_no_revaluation_date_if_needed(cls, indemnification, period,
            end_date, no_revaluation_dates):
        benefit, = indemnification.service.option.current_version.benefits
        if not benefit.revaluation_on_basic_salary_deduction_periods:
            return
        periods_kinds = \
            benefit.revaluation_on_basic_salary_deduction_periods.periods_kinds
        if period.deduction_kind in periods_kinds:
            no_revaluation_dates.append(
                (period.start_date, period.end_date or end_date))

    @classmethod
    def calculation_dates(cls, indemnification, start_date, end_date,
            no_revaluation_dates):
        dates = super(BenefitRule, cls).calculation_dates(indemnification,
            start_date, end_date, no_revaluation_dates)
        loss = indemnification.service.loss
        for period in loss.deduction_periods:
            if start_date <= period.start_date <= end_date:
                dates.add(period.start_date)
                cls._add_no_revaluation_date_if_needed(indemnification, period,
                    end_date, no_revaluation_dates)
            if period.end_date and start_date <= period.end_date <= end_date:
                dates.add(period.end_date + relativedelta(days=1))

        if no_revaluation_dates:
            for reval_start, reval_end in no_revaluation_dates:
                args = {
                    'indemnification_detail_start_date': reval_start,
                    'indemnification_detail_end_date': reval_end,
                    'base_amount': 1,
                    'date': indemnification.start_date,
                    'description': '',
                    }
                indemnification.init_dict_for_rule_engine(args)
                res = indemnification.service.benefit.benefit_rules[
                    0].calculate_revaluation_rule(args)
                for period in res:
                    dates.add(period['start_date'])
        return dates
