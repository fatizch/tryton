# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import model, fields, coog_date
from trytond.modules.currency_cog import ModelCurrency

__all__ = [
    'Loss',
    'DeductionPeriod',
    ]


class Loss:
    __metaclass__ = PoolMeta
    __name__ = 'claim.loss'

    deduction_kinds = fields.Function(
        fields.Many2Many('benefit.loss.description.deduction_period_kind',
            None, None, 'Deduction Kinds'),
        'on_change_with_deduction_kinds')
    deduction_periods = fields.One2Many('claim.loss.deduction.period', 'loss',
        'Deduction Periods', delete_missing=True, domain=[
            ('deduction_kind', 'in', Eval('deduction_kinds'))],
        states={'invisible': ~Eval('deduction_kinds')},
        order=[('deduction_kind', 'ASC'), ('start_date', 'ASC')],
        depends=['deduction_kinds'])

    @fields.depends('loss_desc')
    def on_change_with_deduction_kinds(self, name=None):
        if self.loss_desc:
            return [x.id for x in self.loss_desc.deduction_period_kinds]
        return []


class DeductionPeriod(model.CoogSQL, model.CoogView, ModelCurrency):
    'Deduction Period'

    __name__ = 'claim.loss.deduction.period'

    loss = fields.Many2One('claim.loss', 'Loss', required=True, select=True,
        ondelete='CASCADE')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True,
        domain=[('end_date', '>=', Eval('start_date'))],
        depends=['start_date'])
    deduction_kind = fields.Many2One(
        'benefit.loss.description.deduction_period_kind', 'Deduction Kind',
        required=True, ondelete='RESTRICT')
    amount_kind = fields.Selection([
            ('total', 'Total'), ('per_day', 'Per Day')], 'Amount Kind')
    amount_received = fields.Numeric('Amount Received',
        domain=[('amount_received', '>', 0)],
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    daily_amount = fields.Function(
        fields.Numeric('Daily Amount', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'on_change_with_daily_amount')
    total_amount = fields.Function(
        fields.Numeric('Total Amount', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'on_change_with_total_amount')

    @classmethod
    def __setup__(cls):
        super(DeductionPeriod, cls).__setup__()
        cls.currency = fields.Many2One('currency.currency', 'Currency',
            required=True, ondelete='RESTRICT')

    @classmethod
    def default_amount_kind(cls):
        return 'total'

    @fields.depends('amount_kind', 'amount_received', 'currency', 'end_date',
        'start_date')
    def on_change_with_daily_amount(self, name=None, round=True):
        if self.amount_kind is None:
            return None
        elif self.amount_kind == 'per_day':
            return self.amount_received
        elif self.amount_kind == 'total':
            period_length = Decimal(coog_date.number_of_days_between(
                    self.start_date, self.end_date))
            if round:
                return self.currency.round(
                    self.amount_received / period_length)
            return self.amount_received / period_length
        raise NotImplementedError

    @fields.depends('amount_kind', 'amount_received', 'end_date', 'start_date')
    def on_change_with_total_amount(self, name=None):
        if not self.amount_kind:
            return None
        if self.amount_kind == 'total':
            return self.amount_received
        elif self.amount_kind == 'per_day':
            period_length = Decimal(coog_date.number_of_days_between(
                    self.start_date, self.end_date))
            return self.amount_received * period_length
        raise NotImplementedError

    def get_currency(self):
        return self.currency
