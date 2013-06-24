import copy
import datetime

from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.modules.coop_utils import fields, model, date
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


# Temp : inherit from PaymentTermLine rather than copy-pasting it
class PaymentRuleLine(PaymentTermLine, model.CoopSQL, model.CoopView):
    'Payment Rule Line'

    __name__ = 'billing.payment_rule_line'

    @classmethod
    def __setup__(cls):
        super(PaymentRuleLine, cls).__setup__()
        cls.payment = copy.copy(cls.payment)
        cls.payment.model = 'billing.payment_rule'
        setattr(cls, 'payment', cls.payment)

    def get_line_info(self, start_date):
        return {
            'date': self.get_date(start_date),
            'remaining': self.kind == 'remaining',
            'freq_amount': 0,
            'line': self,
        }


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
    force_line_at_start = fields.Boolean('Force start date line',
        states={'invisible': ~Eval('with_sync_date') or ~~Eval('start_lines')})
    sync_date = fields.Date('Sync Date', states={
        'invisible': ~Eval('with_sync_date'),
        'required': ~~Eval('with_sync_date')})
    start_lines = fields.One2Many('billing.payment_rule_line', 'payment',
        'Start Lines')

    @classmethod
    def default_remaining_position(cls):
        return 'last_calc'

    @classmethod
    def default_with_sync_date(cls):
        return False

    @classmethod
    def default_sync_date(cls):
        Date = Pool().get('ir.date')
        today = Date.today()
        res = datetime.date(today.year, 1, 1)
        return res

    @classmethod
    def default_force_line_at_start(cls):
        return True

    def get_line_dates(self, start_date, end_date):
        dates = [line.get_line_info(start_date) for line in self.start_lines]
        if not dates and self.with_sync_date and self.force_line_at_start:
            dates.append({
                'date': start_date,
                'remaining': self.remaining_position == 'first_calc',
                'freq_amount': 1,
                'line': None})
        last_date = dates[-1]['date'] if len(dates) else start_date
        if self.with_sync_date:
            temp_date = date.add_frequency(self.base_frequency, last_date)
            if self.base_frequency == 'yearly':
                final_date = datetime.date(temp_date.year,
                    self.sync_date.month, self.sync_date.day)
            else:
                final_date = datetime.date(temp_date.year, temp_date.month,
                    self.sync_date.day)
            if final_date <= end_date:
                dates.append({
                    'date': last_date,
                    'remaining': False,
                    'freq_amount': 1,
                    'line': None})
                last_date = final_date
        else:
            last_date = date.add_day(last_date, 1)

        while last_date <= end_date:
            last_date = date.add_frequency(self.base_frequency,
                last_date)
            if last_date <= end_date:
                dates.append({
                    'date': last_date,
                    'remaining': False,
                    'freq_amount': 1,
                    'line': None})

        if self.remaining_position == 'last_calc':
            dates[-1]['remaining'] = True
        return dates

    def compute(self, start_date, end_date, amount, currency, due_date=None):
        lines_dates = self.get_line_dates(start_date, end_date)
        res = dict(((l['date'], 0) for l in lines_dates))
        freq_number = sum([k['freq_amount'] for k in lines_dates])
        remainder = amount
        flat_total = 0
        for line in (l for l in lines_dates if l['line']):
            line_amount = line['line'].get_value(0, 0, currency)
            flat_total += line_amount
            res[line['date']] += line_amount
            remainder -= line_amount

        base_amount = remainder / freq_number
        for elem in (l for l in lines_dates if l['freq_amount']):
            line_amount = currency.round(base_amount * elem['freq_amount'])
            res[elem['date']] += line_amount
            remainder -= line_amount
        if remainder:
            remaining_line = next(l for l in lines_dates if l['remaining'])
            res[remaining_line['date']] += currency.round(remainder)

        return sorted(list(res.iteritems()), key=lambda x: x[0])
