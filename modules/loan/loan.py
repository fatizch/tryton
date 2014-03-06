from decimal import Decimal
from sql.aggregate import Max

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.cog_utils import utils, coop_date, fields, model
from trytond.modules.currency_cog import ModelCurrency

__all__ = [
    'Loan',
    'LoanShare',
    'LoanIncrement',
    'LoanPayment',
    ]

LOAN_KIND = [
    ('fixed_rate', 'Fixed Rate'),
    ('adjustable_rate', 'Adjustable Rate'),
    ('balloon', 'Balloon'),
    ('leasing', 'Leasing'),
    ('graduated', 'Graduated'),
    ('intermediate', 'Intermediate'),
    ('revolving', 'Revolving'),
    ('interest_free', 'Interest Free Loan'),
    ]

DEFFERALS = [
    ('', ''),
    ('partially', 'Partially Deferred'),
    ('fully', 'Fully deferred'),
    ]

LOAN_DURATION_UNIT = [
    ('', ''),
    ('month', 'Month'),
    ('quarter', 'Quarter'),
    ('half_year', 'Half-year'),
    ('year', 'Year'),
    ]


class Loan(model.CoopSQL, model.CoopView, ModelCurrency):
    'Loan'

    __name__ = 'loan'

    order = fields.Integer('Order')
    kind = fields.Selection(LOAN_KIND, 'Kind', required=True, sort=False)
    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE',
        required=True)
    number_of_payments = fields.Integer('Number of Payments', required=True)
    payment_frequency = fields.Selection(LOAN_DURATION_UNIT,
        'Payment Frequency', sort=False, required=True)
    payment_amount = fields.Numeric('Payment Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'],
        states={
            'required': Eval('kind') != 'graduated',
            'invisible': Eval('kind') == 'graduated',
            })
    amount = fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'],
        states={
            'required': Eval('kind') != 'leasing',
            'invisible': Eval('kind') == 'leasing',
            })
    funds_release_date = fields.Date('Funds Release Date', required=True)
    first_payment_date = fields.Date('First Payment Date', required=True)
    loan_shares = fields.One2Many('loan.share', 'loan', 'Loan Shares')
    outstanding_capital = fields.Numeric('Outstanding Capital')
    rate = fields.Numeric('Annual Rate', digits=(16, 4), states={
            'required': Eval('kind').in_(['fixed_rate', 'intermediate']),
            'invisible': ~Eval('kind').in_(['fixed_rate', 'intermediate']),
            })
    payments = fields.One2Many('loan.payment', 'loan',
        'Payments')
    early_payments = fields.One2ManyDomain('loan.payment', 'loan',
        'Early Payments', domain=[('kind', '=', 'early')])
    increments = fields.One2Many('loan.increment', 'loan', 'Increments',
        context={'payment_frequency': Eval('payment_frequency')},
        depends=['payment_frequency'])
    defferal = fields.Function(
        fields.Selection(DEFFERALS, 'Defferal',
            states={'invisible': Eval('kind') == 'leasing'}),
        'get_defferal', 'setter_void')
    defferal_duration = fields.Function(
        fields.Integer('Defferal Duration',
            states={'invisible': ~Eval('defferal')}),
        'get_defferal_duration', 'setter_void')
    first_payment_amount = fields.Function(
        fields.Numeric('First Payment Amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'],
            states={
                'required': Eval('kind') == 'leasing',
                'invisible': Eval('kind') != 'leasing'
                }),
        'get_first_payment_amount', 'setter_void')
    last_payment_amount = fields.Function(
        fields.Numeric('Last Payment Amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'],
            states={
                'required': Eval('kind') == 'leasing',
                'invisible': Eval('kind') != 'leasing'
                }),
        'get_last_payment_amount', 'setter_void')
    end_date = fields.Function(
        fields.Date('End Date'),
        'get_loan_end_date')

    @classmethod
    def __setup__(cls):
        super(Loan, cls).__setup__()
        cls._buttons.update({
                'button_calculate_amortization_table': {},
                })

    @classmethod
    def default_kind(cls):
        return 'fixed_rate'

    @fields.depends('payment_amount', 'kind', 'rate', 'amount',
        'number_of_payments', 'currency', 'payment_frequency',
        'increments')
    def on_change_with_payment_amount(self):
        if self.amount and self.number_of_payments and self.payment_frequency:
            return self.calculate_payment_amount()

    def get_rec_name(self, name):
        res = ''
        if self.amount:
            res = self.currency.amount_as_string(self.amount)
        return res

    def init_from_borrowers(self, parties):
        if hasattr(self, 'loan_shares') and self.loan_shares:
            return
        self.loan_shares = []
        for party in parties:
            share = utils.instanciate_relation(self.__class__, 'loan_shares')
            share.person = party
            self.loan_shares.append(share)

    def init_from_contract(self, contract):
        self.funds_release_date = contract.start_date
        self.first_payment_date = self.on_change_with_first_payment_date()

    @fields.depends('funds_release_date', 'first_payment_date',
        'payment_frequency')
    def on_change_with_first_payment_date(self):
        if self.funds_release_date and self.payment_frequency:
            return coop_date.add_duration(self.funds_release_date,
                self.payment_frequency)

    def get_currency(self):
        if getattr(self, 'contract', None):
            return self.contract.currency

    def get_rate(self, annual_rate=None):
        if not annual_rate:
            annual_rate = self.rate
        if not annual_rate:
            annual_rate = Decimal(0.0)
        coeff = coop_date.convert_frequency(self.payment_frequency, 'year')
        return annual_rate / Decimal(coeff)

    def calculate_payment_amount(self, annual_rate=None,
            number_of_payments=None, amount=None, defferal=None):
        rate = self.get_rate(annual_rate)
        if not number_of_payments:
            number_of_payments = self.number_of_payments
        if not amount:
            amount = self.amount
        if rate:
            if not defferal:
                den = Decimal((1 - (1 + rate) ** -number_of_payments))
                res = amount * rate / den
            elif defferal == 'partially':
                res = amount * rate
            elif defferal == 'fully':
                res = Decimal(0)
        else:
            res = amount / Decimal(number_of_payments)
        return self.currency.round(res)

    def calculate_payments(self):
        Payment = Pool().get('loan.payment')
        res = []
        from_date = self.first_payment_date
        begin_balance = self.amount
        i = 0
        while i < sum([x.number_of_payments for x in self.increments]):
            i += 1
            payment = Payment()
            payment.kind = 'scheduled'
            end_date = coop_date.get_end_of_period(from_date,
                self.payment_frequency)
            payment.calculate(self, from_date, end_date, i, begin_balance,
                self.get_increment(from_date),
                self.get_early_payments_from_date(from_date, end_date))
            res.append(payment)
            from_date = coop_date.add_day(end_date, 1)
            begin_balance = payment.end_balance
        return res

    def calculate_amortization_table(self):
        Payment = Pool().get('loan.payment')
        if getattr(self, 'payments', None):
            Payment.delete(
                [x for x in self.payments if x.kind == 'scheduled' and x.id])
        else:
            self.payments = []
        self.payments = list(self.payments)
        self.payments[:] = [x for x in self.payments
            if x.kind != 'scheduled']
        self.payments += self.calculate_payments()

    @classmethod
    @model.CoopView.button
    def button_calculate_amortization_table(cls, loans):
        for loan in loans:
            loan.calculate_amortization_table()
            loan.save()

    @staticmethod
    def default_payment_frequency():
        return 'month'

    def get_defferal(self, name):
        if not self.increments:
            return ''
        return self.increments[0].defferal

    def get_defferal_duration(self, name):
        if not self.increments:
            return
        return self.increments[0].number_of_payments

    def get_increment(self, at_date):
        increments = [x for x in self.increments
            if x.start_date <= at_date
            and (not x.end_date or x.end_date >= at_date)]
        return increments[0] if increments else None

    def get_early_payments_from_date(self, at_date, to_date):
        return ([x for x in self.early_payments
                if x.start_date >= at_date and x.start_date <= to_date]
            if getattr(self, 'early_payments', None) else [])

    def update_increments(self):
        start_date = self.first_payment_date
        i = 0
        deffered_payments = 0
        for increment in self.increments:
            i += 1
            increment.number = i
            increment.start_date = start_date
            if getattr(increment, 'number_of_payments', None):
                increment.end_date = coop_date.get_end_of_period(start_date,
                    self.payment_frequency, increment.number_of_payments)
            defferal = (increment.defferal
                if hasattr(increment, 'defferal') else None)
            if (not getattr(increment, 'payment_amount', None)
                    and getattr(increment, 'rate', None)):
                increment.payment_amount = self.calculate_payment_amount(
                    increment.rate,
                    self.number_of_payments - deffered_payments,
                    self.amount, defferal)
            if defferal:
                deffered_payments += increment.number_of_payments
            if not utils.is_none(increment, 'number_of_payments'):
                start_date = coop_date.add_day(increment.end_date, 1)

    def create_increment(self, duration=None, payment_amount=None,
            defferal=None):
        Increment = Pool().get('loan.increment')
        res = Increment()
        res.number_of_payments = duration
        res.rate = self.rate
        res.payment_amount = payment_amount
        res.defferal = defferal
        return res

    def create_increments_from_defferal(self, duration=None, defferal=None):
        result = [self.create_increment(duration, defferal=defferal)]
        if defferal is None:
            return result
        result.append(
            self.create_increment(self.number_of_payments - duration))
        return result

    def calculate_increments(self):
        increments = []
        if self.defferal and self.defferal_duration:
            increments = self.create_increments_from_defferal(
                self.defferal_duration, self.defferal)
        elif self.kind == 'intermediate':
            increments = self.create_increments_from_defferal(
                self.number_of_payments - 1, 'partially')
        elif self.kind == 'graduated':
            increments = [self.create_increment()]
        elif self.kind == 'leasing':
            increments = [
                self.create_increment(1, self.first_payment_amount),
                self.create_increment(self.number_of_payments,
                    self.payment_amount),
                self.create_increment(1, self.last_payment_amount)
                ]
        else:
            increments = [self.create_increment(self.number_of_payments)]
        if not hasattr(self, 'increments'):
            self.increments = []
        elif self.increments:
            incs_to_del = set([x for x in self.increments if x.id])
            if incs_to_del:
                Increment = Pool().get('loan.increment')
                Increment.delete(incs_to_del)
        self.increments[:] = increments
        self.update_increments()

    def get_payment(self, at_date=None):
        if not at_date:
            at_date = utils.today()
        payments = [x for x in self.payments
            if x.start_date <= at_date and x.end_date >= at_date
            and x.kind == 'scheduled']
        if len(payments) == 1:
            return payments[0]

    def get_remaining_capital(self, at_date=None):
        payment = self.get_payment(at_date)
        if not payment:
            return 0
        return payment.end_balance

    def init_dict_for_rule_engine(self, current_dict):
        current_dict['loan'] = self

    def get_loan_share(self, party):
        for share in self.loan_shares:
            if share.person == party:
                return share

    @classmethod
    def get_loan_end_date(cls, loans, name):
        pool = Pool()
        cursor = Transaction().cursor
        loan = pool.get('loan').__table__()
        increment = pool.get('loan.increment').__table__()
        query_table = loan.join(increment, type_='LEFT',
            condition=(loan.id == increment.loan))
        cursor.execute(*query_table.select(loan.id, Max(increment.end_date),
                group_by=loan.id))
        return dict(cursor.fetchall())

    def get_publishing_values(self):
        result = super(Loan, self).get_publishing_values()
        result['amount'] = self.amount
        result['start_date'] = self.funds_release_date
        result['number_payments'] = self.number_of_payments
        return result

    def get_first_payment_amount(self, name):
        if not self.increments:
            return
        return self.increments[0].payment_amount

    def get_last_payment_amount(self, name):
        if not self.increments:
            return
        return self.increments[-1].payment_amount


class LoanShare(model.CoopSQL, model.CoopView):
    'Loan Share'

    __name__ = 'loan.share'

    covered_data = fields.Many2One('contract.covered_data', 'Covered Data',
        ondelete='CASCADE')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    loan = fields.Many2One('loan', 'Loan', ondelete='RESTRICT')
    share = fields.Numeric('Loan Share', digits=(16, 4))
    person = fields.Function(
        fields.Many2One('party.party', 'Person'),
        'get_person_id')
    option = fields.Function(
        fields.Many2One('contract.option', 'Contract Option'),
        'get_option_id')
    icon = fields.Function(
        fields.Char('Icon'),
        'get_icon')

    @staticmethod
    def default_share():
        return 1

    def get_name_for_billing(self):
        return '%s %s%% %s' % (self.person.get_rec_name(None),
            str(self.share * 100), self.loan.get_rec_name(None))

    def init_dict_for_rule_engine(self, current_dict):
        self.loan.init_dict_for_rule_engine(current_dict)
        current_dict['share'] = self

    def get_person_id(self, name):
        return self.covered_data.person.id if self.covered_data else None

    def get_option_id(self, name):
        return self.covered_data.option.id if self.covered_data else None

    def init_from_option(self, option):
        self.start_date = option.start_date

    def get_publishing_values(self):
        result = super(LoanShare, self).get_publishing_values()
        result.update(self.loan.get_publishing_values())
        result['share'] = '%.2f %%' % (self.share * 100)
        result['covered_amount'] = self.share * result['amount']
        return result

    def get_icon(self, name):
        return 'loan-interest'

    def get_rec_name(self, name):
        return '%s (%s%%)' % (self.loan.rec_name, self.share * 100)

    def _expand_tree(self, name):
        return True


class LoanIncrement(model.CoopSQL, model.CoopView, ModelCurrency):
    'Loan Increment'

    __name__ = 'loan.increment'

    number = fields.Integer('Number', readonly=True)
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    loan = fields.Many2One('loan', 'Loan', ondelete='CASCADE')
    number_of_payments = fields.Integer('Number of Payments', required=True)
    rate = fields.Numeric('Annual Rate', digits=(16, 4))
    payment_amount = fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    defferal = fields.Selection(DEFFERALS, 'Defferal', sort=False)

    @classmethod
    def __setup__(cls):
        super(LoanIncrement, cls).__setup__()
        cls._order.insert(0, ('number', 'ASC'))

    def get_currency(self):
        return self.loan.currency

    @fields.depends('loan', 'start_date', 'number_of_payments')
    def on_change_with_end_date(self):
        if getattr(self, 'loan', None):
            frequency = self.loan.payment_frequency
        else:
            frequency = Transaction().context.get('payment_frequency')
        return coop_date.get_end_of_period(self.start_date, frequency,
            self.number_of_payments)


class LoanPayment(model.CoopSQL, model.CoopView, ModelCurrency):
    'Loan Payment'

    __name__ = 'loan.payment'

    loan = fields.Many2One('loan', 'Loan', ondelete='CASCADE')
    kind = fields.Selection([
            ('scheduled', 'Scheduled'),
            ('early', 'Early'),
            ('deffered', 'Deffered')], 'Kind')
    number = fields.Integer('Number')
    start_date = fields.Date('Date')
    end_date = fields.Date('End Date')
    begin_balance = fields.Numeric('Begin Balance')
    amount = fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    principal = fields.Numeric('Principal',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    interest = fields.Numeric('Interest',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    end_balance = fields.Function(
        fields.Numeric('End Balance', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_end_balance')

    @classmethod
    def __setup__(cls):
        super(LoanPayment, cls).__setup__()
        cls._order.insert(0, ('start_date', 'ASC'))

    @staticmethod
    def default_kind():
        return 'scheduled'

    def get_currency(self):
        return self.loan.currency

    def calculate(self, loan, at_date, end_date, number, begin_balance,
            increment, early_payments=None):
        rate = loan.get_rate(increment.rate if increment else loan.rate,)
        self.amount = increment.payment_amount
        self.number = number
        self.start_date = at_date
        self.end_date = end_date
        self.begin_balance = begin_balance
        if early_payments:
            self.begin_balance -= sum(map(lambda x: x.amount, early_payments))
        self.interest = (loan.currency.round(begin_balance * rate)
            if rate else None)
        if increment and getattr(increment, 'defferal', None):
            if increment.defferal == 'partially':
                self.principal = Decimal(0.0)
                self.interest = self.amount
            elif increment.defferal == 'fully':
                self.principal = -self.interest
        else:
            if (self.begin_balance > self.amount
                    and number < loan.number_of_payments):
                self.principal = self.amount - self.interest
            else:
                self.principal = self.begin_balance
                if (getattr(self, 'principal', None)
                        and getattr(self, 'interest', None)):
                    self.amount = self.principal + self.interest
        self.end_balance = self.get_end_balance()

    def get_end_balance(self, name=None):
        if self.begin_balance is not None and self.principal is not None:
            return self.begin_balance - self.principal
