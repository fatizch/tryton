import copy
import datetime
from decimal import Decimal

from trytond.pyson import Eval
from tryond.modules.coop_utils import fields, model, date
from trytond.modules.account_invoice import PaymentTermLine
from trytond.modules.insurance_product.business_rule.pricing_rule import \
    PRICING_FREQUENCY


__all__ = [
    'PaymentRuleLine',
    'PaymentRule',
    ]


REMAINING_POSITION = [
    ('', ''),
    ('first_calc', 'First calculated'),
    ('last_calc', 'Last calculated'),
    ]


class PaymentRuleLine(PaymentTermLine, model.CoopSQL, model.CoopView):
    'Payment Rule Line'

    __name__ = 'billing.payment_rule_line'

    @classmethod
    def __setup__(cls):
        super(PaymentRuleLine, cls).__setup__()
        cls.payment = copy.copy(cls.payment)
        cls.payment.model = 'billing.payment_rule'


class PaymentRule(model.CoopSQL, model.CoopView):
    'Payment Rule'

    __name__ = 'billing.payment_rule'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    base_frequency = fields.Selection(PRICING_FREQUENCY, 'Base Frequency',
        required=True)
    remaining_position = fields.Selection(REMAINING_POSITION,
        'Remaining position')
    with_sync_date = fields.Boolean('With Sync Date')
    sync_date = fields.Date('Sync Date', states={
        'invisible': ~Eval('sync_date'),
        'required': ~~Eval('sync_date')})
    start_lines = fields.One2Many('billing.payment_rule_line', 'payment',
        'Start Lines')

    @classmethod
    def default_remaining_position(cls):
        return 'last_calc'

    @classmethod
    def default_with_sync_date(cls):
        today = datetime.date.today()
        res = datetime.date(today.year, 1, 1)
        return res

    def compute(self, start_date, end_date, amount, currency, sync_date=None):
        if not sync_date and self.with_sync_date:
            sync_date = self.sync_date
        res = []
        remainder = amount
        sign = 1 if amount >= Decimal('0.0') else -1
        for line in self.start_lines:
            value = line.get_value(remainder, amount, currency)
            value_date = line.get_date(start_date)
            if not value or not value_date:
                if (not remainder) and line.amount:
                    self.raise_user_error('invalid_line', {
                            'line': line.rec_name,
                            'term': self.rec_name,
                            })
                else:
                    continue
            if ((remainder - value) * sign) < Decimal('0.0'):
                res.append((value_date, remainder))
                break
            res.append((value_date, value))
            remainder -= value
        if not remainder:
            return res
        last_date = res[-1][0] if len(res) else start_date
        new_periods = []
        while last_date <= end_date:
            new_line_start = date.add_day(last_date, 1)
            last_date = date.add_frequency(new_line_start,
                self.base_frequency)
            new_periods.append(new_line_start)
        base_amount = currency.round(remainder / len(new_periods))
        for elem in new_periods:
            res.append((elem, base_amount))
            remainder -= base_amount
        if remainder:
            res[-1][1] += remainder
        return res
