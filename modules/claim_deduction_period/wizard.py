# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import fields


__all__ = [
    'CreateIndemnification',
    'IndemnificationDefinition',
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
        if self.definition.deduction_period_kinds:
            loss = self.definition.service.loss
            per_date = {x.start_date: x for x in loss.deduction_periods}
            periods = []
            for elem in (self.definition.existing_deduction_periods +
                    self.definition.future_deduction_periods):
                if elem.start_date in per_date:
                    elem.id = per_date[elem.start_date].id
                periods.append(elem)
            loss.deduction_periods = periods
            loss.save()
        return super(CreateIndemnification, self).transition_calculate()


class IndemnificationDefinition:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification_definition'

    deduction_period_kinds = fields.Many2Many(
        'benefit.loss.description.deduction_period_kind', None, None,
        'Deduction Kinds')
    existing_deduction_periods = fields.One2Many(
        'claim.loss.deduction.period', None, 'Existing Deduction Periods',
        readonly=True, states={'invisible': ~Eval('deduction_period_kinds')},
        depends=['deduction_period_kinds'])
    future_deduction_periods = fields.One2Many('claim.loss.deduction.period',
        None, 'Future Deduction Periods',
        domain=[('deduction_kind', 'in', Eval('deduction_period_kinds'))],
        states={'invisible': ~Eval('deduction_period_kinds')},
        depends=['deduction_period_kinds'])

    @fields.depends('existing_deduction_periods', 'future_deduction_periods',
        'deduction_period_kinds', 'service', 'start_date')
    def on_change_start_date(self):
        if not self.deduction_period_kinds:
            self.existing_deduction_periods = []
            self.future_deduction_periods = []
            return
        current_futures = {x.start_date: x
            for x in self.future_deduction_periods
            if self.start_date and x.start_date
            and x.start_date >= self.start_date}

        past, futures = [], []
        for period in self.service.loss.deduction_periods:
            if not self.start_date or period.start_date < self.start_date:
                past.append(period)
                continue
            if period.start_date in current_futures:
                futures.append(current_futures.pop(period.start_date))
            else:
                futures.append(period)
        futures += [x for x in self.future_deduction_periods
            if not x.start_date or x.start_date in current_futures]

        self.existing_deduction_periods = [self.new_deduction_period(x)
            for x in past]
        self.future_deduction_periods = [self.new_deduction_period(x)
            for x in futures]

    def new_deduction_period(self, deduction):
        period = Pool().get('claim.loss.deduction.period')()
        for fname in ('start_date', 'end_date', 'amount_received', 'currency',
                'amount_kind', 'currency_digits', 'currency_symbol',
                'deduction_kind'):
            setattr(period, fname, getattr(deduction, fname, None))
        return period
