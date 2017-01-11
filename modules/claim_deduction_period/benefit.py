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


class LossDescription:
    __metaclass__ = PoolMeta
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


class BenefitRule:
    __metaclass__ = PoolMeta
    __name__ = 'benefit.rule'

    @classmethod
    def calculation_dates(cls, indemnification, start_date, end_date):
        dates = super(BenefitRule, cls).calculation_dates(indemnification,
            start_date, end_date)
        loss = indemnification.service.loss
        for period in loss.deduction_periods:
            if start_date <= period.start_date <= end_date:
                dates.add(period.start_date)
            if start_date <= period.end_date <= end_date:
                dates.add(period.end_date + relativedelta(days=1))
        return dates
