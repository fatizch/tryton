import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.modules.cog_utils import fields, model, coop_date
from trytond.modules.offered_insurance.business_rule.premium_rule import \
    PRICING_FREQUENCY

__all__ = [
    'PaymentTermLine',
    'PaymentTermFeeRelation',
    'PaymentTerm',
    ]

PAYMENT_FREQUENCY = PRICING_FREQUENCY[::1]

REMAINING_POSITION = [
    ('', ''),
    ('first_calc', 'First calculated'),
    ('last_calc', 'Last calculated'),
    ('custom', 'Custom Lines'),
    ]

PAYMENT_DELAYS = [
    ('in_arrears', 'In Arrears'),
    ('in_advance', 'In Advance'),
    ]

SPLIT_METHODS = [
    ('proportional', 'Proportional Periods'),
    ('equal', 'Equal Periods'),
    ]


class PaymentTermLine(model.CoopSQL, model.CoopView):
    'Payment Term Line'

    __name__ = 'billing.payment.term.line'

    sequence = fields.Integer('Sequence')
    payment_term = fields.Many2One('billing.payment.term', 'Payment Term',
        required=True, ondelete='CASCADE')
    type = fields.Selection([
            ('fixed', 'Fixed'),
            ('percent_on_total', 'Percentage on Total'),
            ('prorata', 'Prorata'),
            ], 'Type', required=True,
        on_change=['type'])
    percentage = fields.Numeric('Percentage', digits=(16, 8),
        states={
            'invisible': Eval('type', '') != 'percent_on_total',
            'required': Eval('type', '') == 'percent_on_total'
            }, on_change=['percentage'], depends=['type'])
    divisor = fields.Numeric('Divisor', digits=(16, 8),
        states={
            'invisible': Eval('type', '') != 'percent_on_total',
            'required': Eval('type', '') == 'percent_on_total',
            }, on_change=['divisor'], depends=['type'])
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        states={
            'invisible': Eval('type', '') != 'fixed',
            'required': Eval('type', '') == 'fixed',
            }, depends=['type', 'currency_digits'])
    currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'invisible': Eval('type', '') != 'fixed',
            'required': Eval('type', '') == 'fixed',
            }, depends=['type'], ondelete='RESTRICT')
    currency_digits = fields.Function(fields.Integer('Currency Digits',
            on_change_with=['currency']), 'on_change_with_currency_digits')
    day = fields.Integer('Day of Month')
    month = fields.Selection([
            (None, ''),
            ('1', 'January'),
            ('2', 'February'),
            ('3', 'March'),
            ('4', 'April'),
            ('5', 'May'),
            ('6', 'June'),
            ('7', 'July'),
            ('8', 'August'),
            ('9', 'September'),
            ('10', 'October'),
            ('11', 'November'),
            ('12', 'December'),
            ], 'Month', sort=False)
    weekday = fields.Selection([
            (None, ''),
            ('0', 'Monday'),
            ('1', 'Tuesday'),
            ('2', 'Wednesday'),
            ('3', 'Thursday'),
            ('4', 'Friday'),
            ('5', 'Saturday'),
            ('6', 'Sunday'),
            ], 'Day of Week', sort=False)
    months = fields.Integer('Number of Months', required=True)
    weeks = fields.Integer('Number of Weeks', required=True)
    days = fields.Integer('Number of Days', required=True)
    add_calculated_period = fields.Boolean('Add calculated period',
        on_change=['add_calculated_period'])
    number_of_periods = fields.Numeric('Number of periods', digits=(16, 2),
        states={
            'invisible': ~Eval('add_calculated_period'),
            'required': ~~Eval('add_calculated_period')})
    is_remainder = fields.Boolean('Is remainder',
        states={'invisible':
            Eval('_parent_payment_term', {}).get('remaining_position', '')
            != 'custom'})

    @classmethod
    def order_sequence(cls, tables):
        rule_line, _ = tables[None]
        return [rule_line.sequence is None, rule_line.sequence]

    @classmethod
    def default_add_calculated_period(cls):
        return False

    @classmethod
    def default_number_of_periods(cls):
        return 1

    @classmethod
    def default_is_remainder(cls):
        return False

    @staticmethod
    def default_currency_digits():
        return 2

    @staticmethod
    def default_type():
        return 'fixed'

    @staticmethod
    def default_months():
        return 0

    @staticmethod
    def default_weeks():
        return 0

    @staticmethod
    def default_days():
        return 0

    def on_change_add_calculated_period(self):
        res = {}
        if (hasattr(self, 'add_calculated_period') and
                self.add_calculated_period):
            res['number_of_periods'] = 1
        return res

    def on_change_type(self):
        res = {}
        if self.type != 'fixed':
            res['amount'] = Decimal('0.0')
            res['currency'] = None
        if self.type != 'percent_on_total':
            res['percentage'] = Decimal('0.0')
            res['divisor'] = Decimal('0.0')
        return res

    def on_change_percentage(self):
        if not self.percentage:
            return {'divisor': 0.0}
        return {
            'divisor': self.round(Decimal('100.0') / self.percentage,
                self.__class__.divisor.digits[1]),
            }

    def on_change_divisor(self):
        if not self.divisor:
            return {'percentage': 0.0}
        return {
            'percentage': self.round(Decimal('100.0') / self.divisor,
                self.__class__.percentage.digits[1]),
            }

    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    def get_delta(self):
        return {
            'day': self.day,
            'month': int(self.month) if self.month else None,
            'days': self.days,
            'weeks': self.weeks,
            'months': self.months,
            'weekday': int(self.weekday) if self.weekday else None,
            }

    def get_date(self, date):
        return date + relativedelta(**self.get_delta())

    def get_flat_value(self, start_date, end_date, amount, currency):
        Currency = Pool().get('currency.currency')
        if self.type == 'fixed':
            return Currency.compute(self.currency, self.amount, currency)
        elif self.type == 'percent_on_total':
            return currency.round(amount * self.percentage / Decimal('100'))
        elif self.type == 'prorata':
            payment_term = self.payment_term
            my_start_date = self.get_date(start_date)
            if payment_term.with_sync_date:
                temp_date = coop_date.add_frequency(
                    payment_term.base_frequency, my_start_date)
                if payment_term.base_frequency == 'yearly':
                    final_date = datetime.date(temp_date.year,
                        payment_term.sync_date.month,
                        payment_term.sync_date.day)
                else:
                    final_date = datetime.date(temp_date.year, temp_date.month,
                        payment_term.sync_date.day)
                if final_date <= end_date:
                    my_end_date = final_date
                else:
                    my_end_date = end_date
            else:
                my_end_date = coop_date.add_frequency(
                    payment_term.base_frequency, my_start_date)
            my_end_date = coop_date.add_day(my_end_date, -1)
            period = coop_date.number_of_days_between(
                my_start_date, my_end_date)
            total_period = coop_date.number_of_days_between(
                start_date, end_date)
            return currency.round(amount * period / total_period)
        return 0

    @staticmethod
    def round(number, digits):
        quantize = Decimal(10) ** -Decimal(digits)
        return Decimal(number).quantize(quantize)

    def get_line_info(self, start_date):
        return {
            'date': self.get_date(start_date),
            'remaining': self.is_remainder,
            'freq_amount': self.number_of_periods if self.add_calculated_period
            else 0,
            'line': self,
            }


class PaymentTermFeeRelation(model.CoopSQL):
    'Payment Term - Fee relation'

    __name__ = 'billing.payment.term-fee'

    payment_term = fields.Many2One('billing.payment.term', 'Payment Term',
        required=True, ondelete='CASCADE')
    fee = fields.Many2One('account.fee.description', 'Fee', required=True,
        ondelete='RESTRICT')


class PaymentTerm(model.CoopSQL, model.CoopView):
    'Payment Term'

    __name__ = 'billing.payment.term'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    base_frequency = fields.Selection(PAYMENT_FREQUENCY, 'Base Frequency',
        required=True, on_change=['base_frequency', 'start_lines'])
    remaining_position = fields.Selection(REMAINING_POSITION,
        'Remaining position', states={
            'invisible': Eval('base_frequency', '') == 'one_shot'})
    with_sync_date = fields.Boolean('With Sync Date', states={
            'invisible': Eval('base_frequency', '') == 'one_shot'})
    force_line_at_start = fields.Boolean('Force start date line',
        states={'invisible': ~Eval('with_sync_date') or ~~Eval('start_lines')
            or Eval('base_frequency', '') == 'one_shot'})
    sync_date = fields.Date('Sync Date', states={
            'invisible': ~Eval('with_sync_date') or Eval('base_frequency', '')
            == 'one_shot',
            'required': ~~Eval('with_sync_date')})
    start_lines = fields.One2Many('billing.payment.term.line', 'payment_term',
        'Start Lines', states={
            'invisible': Eval('base_frequency', '') == 'one_shot'})
    appliable_fees = fields.Many2Many('billing.payment.term-fee',
        'payment_term', 'fee', 'Appliable fees', depends=['company'],
        domain=[('company', '=', Eval('company'))])
    payment_mode = fields.Selection(PAYMENT_DELAYS, 'Payment Mode', states={
            'invisible': Eval('base_frequency', '') == 'one_shot'})
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='RESTRICT')
    split_method = fields.Selection(SPLIT_METHODS, 'Splitting method', states={
            'invisible': Eval('base_frequency', '') == 'one_shot'})

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company') or None

    @classmethod
    def default_payment_mode(cls):
        return 'in_advance'

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

    def on_change_base_frequency(self):
        if self.base_frequency != 'one_shot':
            return {}
        return {
            'payment_mode': 'in_advance',
            'start_lines': {'remove': [x.id for x in self.start_lines]},
            }

    @classmethod
    def default_split_method(cls):
        return 'proportional'

    def get_line_dates(self, start_date, end_date):
        if self.base_frequency == 'one_shot':
            return [{
                    'date': start_date,
                    'remaining': True,
                    'freq_amount': 0,
                    'line': None}]
        dates = [line.get_line_info(start_date) for line in self.start_lines]
        if not dates and self.with_sync_date and self.force_line_at_start:
            dates.append({
                    'date': start_date,
                    'remaining': self.remaining_position == 'first_calc',
                    'freq_amount': 1,
                    'line': None})
        last_date = dates[-1]['date'] if len(dates) else start_date
        first_calculated = False
        if self.with_sync_date:
            temp_date = coop_date.add_frequency(self.base_frequency, last_date)
            if self.base_frequency == 'yearly':
                final_date = datetime.date(temp_date.year,
                    self.sync_date.month, self.sync_date.day)
            else:
                final_date = datetime.date(temp_date.year, temp_date.month,
                    self.sync_date.day)
            if final_date <= end_date:
                dates.append({
                        'date': final_date,
                        'remaining': self.remaining_position == 'first_calc',
                        'freq_amount': 1,
                        'line': None})
                first_calculated = True
                last_date = final_date
        else:
            last_date = coop_date.add_day(last_date, 1)

        while last_date <= end_date:
            last_date = coop_date.add_frequency(self.base_frequency,
                last_date)
            if last_date <= end_date:
                dates.append({
                        'date': last_date,
                        'remaining': (self.remaining_position == 'first_calc'
                            and not first_calculated),
                        'freq_amount': 1,
                        'line': None})
                first_calculated = True

        if not dates:
            dates.append({
                    'date': start_date,
                    'remaining': True,
                    'freq_amount': 1,
                    'line': None})

        if self.remaining_position == 'last_calc':
            dates[-1]['remaining'] = True
        return dates

    def apply_payment_date(self, payments, payment_date):
        if not payment_date:
            return payments
        res = []
        for cur_date, amount in payments:
            if self.payment_mode == 'in_advance':
                if not res:
                    # First date:
                    res.append((cur_date, amount))
                    continue
                if payment_date > cur_date.day:
                    temp_date = coop_date.add_month(cur_date, -1)
                    if payment_date > 28:
                        temp_date = coop_date.get_end_of_month(temp_date)
                        if temp_date.day > payment_date:
                            res.append((datetime.date(temp_date.year,
                                        temp_date.month, payment_date),
                                    amount))
                        else:
                            res.append((temp_date, amount))
                    else:
                        res.append((datetime.date(temp_date.year,
                                    temp_date.month, payment_date), amount))
                else:
                    res.append((datetime.date(cur_date.year, cur_date.month,
                                payment_date), amount))
            elif self.payment_mode == 'in_arrears':
                if payment_date > cur_date.day:
                    if payment_date > 28:
                        temp_date = coop_date.get_end_of_month(cur_date)
                        if temp_date.day > payment_date:
                            res.append((datetime.date(temp_date.year,
                                        temp_date.month, payment_date),
                                    amount))
                        else:
                            res.append((temp_date, amount))
                    else:
                        res.append((datetime.date(cur_date.year,
                                    cur_date.month, payment_date), amount))
                else:
                    temp_date = coop_date.add_month(cur_date, 1)
                    if payment_date >= temp_date.day:
                        res.append((temp_date, amount))
                    else:
                        res.append((datetime.date(temp_date.year,
                                    temp_date.month, payment_date), amount))
        return res

    def compute(self, work_set):
        lines_dates = self.get_line_dates(work_set.period[0],
            work_set.period[1])
        res = dict(((l['date'], 0) for l in lines_dates))
        freq_number = sum([k['freq_amount'] for k in lines_dates])
        remainder = work_set.total_amount
        flat_total = 0
        for line in (l for l in lines_dates if l['line']):
            line_amount = line['line'].get_flat_value(work_set.period[0],
                work_set.period[1], work_set.total_amount, work_set.currency)
            flat_total += line_amount
            res[line['date']] += line_amount
            remainder -= line_amount
        base_amount = remainder / freq_number if freq_number else remainder
        exact_day_price = remainder / coop_date.number_of_days_between(
            work_set.period[0], work_set.period[1])
        periods = []
        for idx, elem in enumerate([l for l in lines_dates
                    if l['freq_amount']] + [{'date': coop_date.add_day(
                            work_set.period[1], 1)}]):
            if idx != 0:
                periods[idx - 1][1] = coop_date.add_day(elem['date'], -1)
            if elem['date'] == coop_date.add_day(work_set.period[1], 1):
                continue
            periods.append([elem['date'], None, elem])
        for start_date, end_date, elem in periods:
            if (self.split_method == 'equal' or self.base_frequency ==
                    'one_shot'):
                line_amount = work_set.currency.round(base_amount *
                    elem['freq_amount'])
            elif self.split_method == 'proportional':
                line_amount = work_set.currency.round(exact_day_price *
                    coop_date.number_of_days_between(start_date, end_date))
            res[start_date] += line_amount
            remainder -= line_amount
        if remainder:
            remaining_line = next(l for l in lines_dates if l['remaining'])
            res[remaining_line['date']] += work_set.currency.round(remainder)

        result = sorted(list((x for x in res.iteritems() if x[1])),
            key=lambda x: x[0])
        return self.apply_payment_date(result, work_set.payment_date)
