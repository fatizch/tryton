# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import fields
from trytond.modules.claim_deduction_period.claim import DeductionPeriod

__all__ = [
    'CreateIndemnification',
    'IndemnificationDefinition',
    'DeductionPeriodDisplay',
    ]


class CreateIndemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.create_indemnification'

    def default_definition(self, name):
        defaults = super(CreateIndemnification, self).default_definition(name)
        if not defaults.get('service', None):
            return defaults
        service = Pool().get('claim.service')(defaults['service'])
        defaults['deduction_period_kinds'] = [
            x.id for x in service.loss.deduction_kinds]
        return defaults

    def transition_calculate(self):
        Deduction = Pool().get('claim.loss.deduction.period')
        if self.definition.deduction_period_kinds:
            loss = self.definition.service.loss
            updated_deduction_periods = {x.id: x
                for x in loss.deduction_periods}
            new_deductions = []
            for elem in self.definition.deduction_periods:
                if not getattr(elem, 'start_date', None):
                    elem.start_date = self.definition.start_date
                if not getattr(elem, 'end_date', None):
                    elem.end_date = self.definition.end_date
                if elem.deduction_id:
                    updated = Deduction(elem.deduction_id)
                    elem.update_deduction(updated)
                    updated_deduction_periods[elem.deduction_id] = updated
                else:
                    new_deduction = Deduction()
                    elem.update_deduction(new_deduction)
                    new_deductions.append(new_deduction)
            loss.deduction_periods = tuple(updated_deduction_periods.values() +
                new_deductions)
            loss.save()
        return super(CreateIndemnification, self).transition_calculate()


class IndemnificationDefinition:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification_definition'

    deduction_period_kinds = fields.Many2Many(
        'benefit.loss.description.deduction_period_kind', None, None,
        'Deduction Kinds')
    deduction_periods = fields.One2Many('claim.loss.deduction.period.display',
        None, 'Deduction Periods',
        domain=[('deduction_kind', 'in', Eval('deduction_period_kinds'))],
        states={'invisible': ~Eval('deduction_period_kinds')},
        depends=['deduction_period_kinds'])

    @fields.depends('deduction_periods', 'deduction_period_kinds', 'service',
        'start_date', 'end_date')
    def on_change_start_date(self):
        if not self.deduction_period_kinds:
            self.deduction_periods = []
            return

        in_period_deduction = [x for x in self.deduction_periods
            if self.start_date and not x.deduction_id and (
                x.start_date and x.start_date >= self.start_date or
                x.end_date and x.end_date >= self.end_date)]

        for period in self.service.loss.deduction_periods:
            if self.start_date and (period.start_date and
                    period.start_date >= self.start_date or
                    period.end_date and period.end_date >= self.end_date):
                in_period_deduction.append(period)

        self.deduction_periods = [self.new_deduction_period(x)
            for x in in_period_deduction]

    def new_deduction_period(self, deduction):
        period = Pool().get('claim.loss.deduction.period.display')()
        period.init_from_deduction(deduction)
        return period


class DeductionPeriodDisplay(DeductionPeriod):
    'Deduction Period Display'
    __name__ = 'claim.loss.deduction.period.display'

    deduction_id = fields.Integer('Deduction ID')

    @classmethod
    def __setup__(cls):
        super(DeductionPeriodDisplay, cls).__setup__()
        cls.start_date.required = False

    @staticmethod
    def table_query():
        # This is used only to not create the table in database
        return True

    @classmethod
    def common_field_with_deduction(cls):
        return ('start_date', 'end_date', 'amount_received', 'currency',
                'amount_kind', 'currency_digits', 'currency_symbol',
                'deduction_kind')

    def init_from_deduction(self, deduction):
        for fname in self.__class__.common_field_with_deduction():
            setattr(self, fname, getattr(deduction, fname, None))
        if deduction.id:
            self.deduction_id = deduction.id

    def update_deduction(self, deduction):
        for fname in self.__class__.common_field_with_deduction():
            setattr(deduction, fname, getattr(self, fname, None))
