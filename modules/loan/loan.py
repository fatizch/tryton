from decimal import Decimal

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval, And, Or, Bool, Len, If

from trytond.modules.cog_utils import utils, coop_date, fields, model
from trytond.modules.cog_utils import coop_string
from trytond.modules.currency_cog import ModelCurrency

__all__ = [
    'Loan',
    'LoanIncrement',
    'LoanPayment',
    'LoanParty',
    ]

LOAN_KIND = [
    ('fixed_rate', 'Fixed Rate'),
    ('balloon', 'Balloon'),
    ('leasing', 'Leasing'),
    ('graduated', 'Graduated'),
    ('intermediate', 'Intermediate'),
    ('interest_free', 'Interest Free Loan'),
    ]

DEFERALS = [
    ('', ''),
    ('partially', 'Partially Deferred'),
    ('fully', 'Fully deferred'),
    ]


class Loan(model.CoopSQL, model.CoopView):
    'Loan'

    __name__ = 'loan'
    _rec_name = 'number'

    number = fields.Char('Number', required=True, readonly=True, select=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True, ondelete='RESTRICT',
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        )
    kind = fields.Selection(LOAN_KIND, 'Kind', required=True, sort=False)
    currency = fields.Many2One('currency.currency', 'Currency',
        ondelete='RESTRICT')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'),
        'on_change_with_currency_symbol')
    number_of_payments = fields.Integer('Number of Payments', required=True)
    payment_frequency = fields.Selection(coop_date.DAILY_DURATION,
        'Payment Frequency', sort=False, required=True,
        domain=[('payment_frequency', 'in',
                ['month', 'quarter', 'half_year', 'year'])])
    payment_amount = fields.Numeric('Payment Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'],
        states={
            'required': And(Eval('kind') != 'graduated', ~Eval('deferal')),
            'invisible': Or(Eval('kind') == 'graduated', ~~Eval('deferal')),
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
    parties = fields.Many2Many('loan-party', 'loan', 'party', 'Parties',
        required=True)
    rate = fields.Numeric('Annual Rate', digits=(16, 4),
        states={
            'required': Eval('kind').in_(
                ['fixed_rate', 'intermediate', 'balloon']),
            'invisible': ~Eval('kind').in_(
                ['fixed_rate', 'intermediate', 'balloon', 'graduated']),
            },
        domain=[If(
                Eval('kind').in_(['fixed_rate', 'intermediate', 'balloon']),
                ['OR', ('rate', '>', 0), ('rate', '=', None)],
                [],
                )],
        depends=['kind'])
    payments = fields.One2Many('loan.payment', 'loan',
        'Payments')
    increments = fields.One2Many('loan.increment', 'loan', 'Increments',
        context={
            'payment_frequency': Eval('payment_frequency'),
            'increments_end_date': Eval('increments_end_date'),
            'start_date': Eval('first_payment_date'),
            'end_date': Eval('end_date'),
            'rate': Eval('rate'),
            'number': Len(Eval('increments', [])),
            },
        depends=['payment_frequency', 'increments_end_date', 'rate',
            'first_payment_date', 'end_date', 'increments',
            'number_of_payments'])
    deferal = fields.Function(
        fields.Selection(DEFERALS, 'Deferal', states={
                'invisible': Eval('kind').in_(
                    ['leasing', 'graduated']),
                }),
        'get_deferal', 'setter_void')
    deferal_duration = fields.Function(
        fields.Integer('Deferal Duration',
            states={
                'invisible': ~Eval('deferal'),
                'required': Bool(Eval('deferal', '')),
                }),
        'get_deferal_duration', 'setter_void')
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
    increments_end_date = fields.Function(
        fields.Date('Increments End Date', states={'invisible': True}),
        'on_change_with_increments_end_date')
    end_date = fields.Function(
        fields.Date('End Date'),
        'get_end_date')
    current_loan_shares = fields.Function(
        fields.One2Many('loan.share', None, 'Current Loan Share'),
        'get_current_loan_shares')
    order = fields.Function(
        fields.Integer('Order'),
        'get_order')
    outstanding_balance = fields.Function(
        fields.Numeric('Outstanding Balance',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_outstanding_loan_balance')

    @classmethod
    def __setup__(cls):
        super(Loan, cls).__setup__()
        cls._order.insert(0, ('number', 'ASC'))
        cls._buttons.update({
                'button_calculate_amortization_table': {},
                })
        cls._error_messages.update({
                'invalid_number_of_payments_sum': (
                    'The sum of increments number of payments (%s) does not '
                    'match the loan number of payments (%s)'),
                'no_sequence': 'No loan sequence defined',
                })

    @classmethod
    def create(cls, vlist):
        Sequence = Pool().get('ir.sequence')
        with Transaction().set_user(0):
            loan_sequences = Sequence.search([('code', '=', 'loan')])
        sequences_dict = dict([(x.company.id, x) for x in loan_sequences])
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if not vals.get('number'):
                sequence = sequences_dict.get(vals.get('company'), None)
                if not sequence:
                    cls.raise_user_error('no_sequence')
                vals['number'] = Sequence.get_id(sequence.id)
        return super(Loan, cls).create(vlist)

    @classmethod
    def validate(cls, loans):
        super(Loan, cls).validate(loans)
        for loan in loans:
            loan.check_increments()

    def pre_validate(self):
        super(Loan, self).pre_validate()
        self.check_increments()

    def check_increments(self):
        the_sum = sum([x.number_of_payments for x in self.increments])
        if not the_sum == self.number_of_payments:
            self.raise_user_error('invalid_number_of_payments_sum',
                (the_sum, self.number_of_payments))

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_currency():
        if Transaction().context.get('company'):
            Company = Pool().get('company.company')
            company = Company(Transaction().context['company'])
            return company.currency.id

    @classmethod
    def default_kind(cls):
        return 'fixed_rate'

    @classmethod
    def default_parties(cls):
        party = Transaction().context.get('party', None)
        return [party] if party else []

    @fields.depends('payment_amount', 'kind', 'rate', 'amount',
        'number_of_payments', 'currency', 'payment_frequency',
        'increments', 'deferal', 'deferal_duration')
    def on_change_with_payment_amount(self):
        if (self.amount and self.number_of_payments and self.payment_frequency
                and not self.deferal):
            return self.calculate_payment_amount()
        else:
            return None

    def get_current_loan_shares(self, name):
        contract_id = Transaction().context.get('contract', None)
        if not contract_id:
            return []
        return [x.id for x in Pool().get('loan.share').search([
                    ('loan', '=', self.id),
                    ('contract', '=', contract_id)])]

    def get_rec_name(self, name):
        name = []
        if self.number:
            name.append(self.number)
        if self.kind:
            name.append(coop_string.translate_value(self, 'kind'))
        if self.amount:
            name.append(self.currency.amount_as_string(self.amount))
        return ' '.join(name)

    def get_order(self, name):
        contract_id = Transaction().context.get('contract', None)
        if not contract_id:
            return None
        contract = Pool().get('contract')(contract_id)
        for idx, loan in enumerate(contract.used_loans, 1):
            if loan == self:
                return idx
        return None

    def init_from_borrowers(self, parties):
        if hasattr(self, 'loan_shares') and self.loan_shares:
            return
        self.loan_shares = []
        LoanShare = Pool().get('loan.share')
        for party in parties:
            share = LoanShare()
            share.person = party
            self.loan_shares.append(share)

    @fields.depends('funds_release_date', 'payment_frequency',
        'first_payment_date')
    def on_change_with_first_payment_date(self):
        if self.funds_release_date and self.payment_frequency:
            return coop_date.add_duration(self.funds_release_date,
                self.payment_frequency)
        else:
            return self.first_payment_date

    def get_rate(self, annual_rate=None):
        if not annual_rate:
            annual_rate = self.rate
        if not annual_rate:
            annual_rate = Decimal(0)
        coeff = coop_date.convert_frequency(self.payment_frequency, 'year')
        return annual_rate / Decimal(coeff)

    def calculate_payment_amount(self, annual_rate=None,
            number_of_payments=None, amount=None, deferal=None):
        rate = self.get_rate(annual_rate)
        if not number_of_payments:
            number_of_payments = self.number_of_payments
        if not amount:
            amount = self.amount
        if not deferal:
            if rate:
                den = Decimal((1 - (1 + rate) ** -number_of_payments))
                res = amount * rate / den
            else:
                res = amount / Decimal(number_of_payments)
        elif deferal == 'partially':
            res = amount * rate
        elif deferal == 'fully':
            res = Decimal(0)
        return self.currency.round(res)

    def calculate_payments(self):
        Payment = Pool().get('loan.payment')
        res = [Payment(
                kind='releasing_funds',
                number=0,
                start_date=self.funds_release_date,
                outstanding_balance=self.amount,
                )]
        from_date = self.first_payment_date
        begin_balance = self.amount
        i = 0
        for increment in self.increments:
            increment.begin_balance = begin_balance
            if increment.begin_balance and not increment.payment_amount:
                increment.payment_amount = self.calculate_payment_amount(
                    increment.rate, increment.number_of_payments,
                    increment.begin_balance, increment.deferal)
            for j in range(increment.number_of_payments):
                i += 1
                payment = Payment()
                payment.kind = 'scheduled'
                from_date = coop_date.add_duration(increment.start_date,
                    self.payment_frequency, j)
                payment.calculate(self, from_date, i, begin_balance,
                    increment)
                res.append(payment)
                begin_balance = payment.outstanding_balance
        return res

    def calculate_amortization_table(self):
        Payment = Pool().get('loan.payment')
        if getattr(self, 'payments', None):
            Payment.delete([x for x in self.payments if x.id])
        self.payments = self.calculate_payments()

    @classmethod
    @model.CoopView.button
    def button_calculate_amortization_table(cls, loans):
        LoanPayment = Pool().get('loan.payment')
        with Transaction().set_user(0):
            vals = []
            for loan in loans:
                loan.calculate_amortization_table()
                vals += [x._save_values for x in loan.payments]
                for payment in vals:
                    payment['loan'] = loan.id
            LoanPayment.create(vals)

    @staticmethod
    def default_payment_frequency():
        return 'month'

    def get_deferal(self, name):
        if self.increments:
            return self.increments[0].deferal

    def get_deferal_duration(self, name):
        if self.deferal:
            return self.increments[0].number_of_payments

    def update_increments(self):
        start_date = self.first_payment_date
        i = 0
        for increment in self.increments:
            i += 1
            increment.number = i
            increment.start_date = start_date
            if getattr(increment, 'number_of_payments', None):
                increment.end_date = coop_date.add_duration(start_date,
                    self.payment_frequency, increment.number_of_payments - 1)
                start_date = coop_date.add_duration(increment.end_date,
                    self.payment_frequency, 1)

    def create_increment(self, duration=None, payment_amount=None,
            deferal=None):
        Increment = Pool().get('loan.increment')
        res = Increment()
        res.number_of_payments = duration
        res.rate = self.rate
        res.payment_amount = payment_amount
        res.deferal = deferal
        return res

    def create_increments_from_deferal(self, duration=None, deferal=None):
        result = [self.create_increment(duration, deferal=deferal)]
        if deferal is None:
            return result
        result.append(
            self.create_increment(self.number_of_payments - duration))
        return result

    def calculate_increments(self):
        if self.kind == 'graduated':
            return
        increments = []
        if self.deferal and self.deferal_duration:
            increments = self.create_increments_from_deferal(
                self.deferal_duration, self.deferal)
        elif self.kind == 'leasing':
            increments = [
                self.create_increment(1, self.first_payment_amount),
                self.create_increment(self.number_of_payments - 2,
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
        for payment in reversed(self.payments):
            if payment.start_date <= at_date:
                return payment

    def get_outstanding_loan_balance(self, name=None, at_date=None):
        payment = self.get_payment(at_date)
        return payment.outstanding_balance if payment else None

    def init_dict_for_rule_engine(self, current_dict):
        current_dict['loan'] = self

    def get_loan_share(self, party):
        for share in self.loan_shares:
            if share.person == party:
                return share

    @fields.depends('increments', 'end_date')
    def on_change_with_end_date(self, name=None):
        if getattr(self, 'increments', None):
            return self.increments[-1].end_date
        return self.end_date

    def get_publishing_values(self):
        result = super(Loan, self).get_publishing_values()
        result['amount'] = self.amount
        result['start_date'] = self.funds_release_date
        result['number_payments'] = self.number_of_payments
        return result

    def get_first_payment_amount(self, name):
        if self.increments:
            return self.increments[0].payment_amount

    def get_last_payment_amount(self, name):
        if self.increments:
            return self.increments[-1].payment_amount

    @fields.depends('kind', 'deferal')
    def on_change_with_deferal(self):
        if self.kind in ['intermediate', 'balloon']:
            return 'partially'
        elif self.kind in ['leasing', 'interest_free', 'graduated']:
            return
        else:
            return self.deferal

    @fields.depends('kind', 'number_of_payments', 'deferal_duration')
    def on_change_with_deferal_duration(self):
        if self.kind in ['intermediate', 'balloon']:
            return (self.number_of_payments - 1
                if self.number_of_payments else None)
        elif self.kind in ['leasing', 'interest_free', 'graduated']:
            return
        else:
            return self.deferal_duration

    @fields.depends('kind')
    def on_change_with_rate(self):
        if self.kind == 'interest_free':
            return Decimal(0)

    @fields.depends('increments')
    def on_change_with_increments_end_date(self, name=None):
        if self.increments:
            return self.increments[-1].end_date

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        return self.currency.digits if self.currency else 2

    @fields.depends('currency')
    def on_change_with_currency_symbol(self, name=None):
        return self.currency.symbol if self.currency else ''

    def get_end_date(self, name):
        return self.increments[-1].end_date if self.increments else None


class LoanIncrement(model.CoopSQL, model.CoopView, ModelCurrency):
    'Loan Increment'

    __name__ = 'loan.increment'

    number = fields.Integer('Number')
    begin_balance = fields.Numeric('Begin Balance',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Function(
        fields.Date('End Date'),
        'get_end_date')
    loan = fields.Many2One('loan', 'Loan', ondelete='CASCADE')
    number_of_payments = fields.Integer('Number of Payments', required=True)
    rate = fields.Numeric('Annual Rate', digits=(16, 4))
    payment_amount = fields.Numeric('Amount', required=True,
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    deferal = fields.Selection(DEFERALS, 'Deferal', sort=False)

    @classmethod
    def __setup__(cls):
        super(LoanIncrement, cls).__setup__()
        cls._order.insert(0, ('number', 'ASC'))

    def pre_validate(self):
        super(LoanIncrement, self).pre_validate()

    def get_currency(self):
        return self.loan.currency

    @fields.depends('loan', 'start_date', 'number_of_payments', 'end_date')
    def on_change_with_end_date(self, name=None):
        if getattr(self, 'loan', None):
            frequency = self.loan.payment_frequency
        else:
            frequency = Transaction().context.get('payment_frequency')
        if not frequency or not self.number_of_payments:
            return self.end_date
        return coop_date.add_duration(self.start_date, frequency,
            self.number_of_payments - 1)

    @staticmethod
    def default_start_date():
        increments_end_date = Transaction().context.get('increments_end_date')
        if increments_end_date:
            return coop_date.add_duration(increments_end_date,
                Transaction().context.get('payment_frequency'), 1)
        else:
            return Transaction().context.get('start_date')

    @staticmethod
    def default_rate():
        return Transaction().context.get('rate', None)

    @staticmethod
    def default_number_of_payments():
        return 0

    @staticmethod
    def default_number():
        return Transaction().context.get('number', 0) + 1

    def get_end_date(self, name):
        return coop_date.add_duration(self.start_date,
            self.loan.payment_frequency, self.number_of_payments - 1)


class LoanPayment(model.CoopSQL, model.CoopView, ModelCurrency):
    'Loan Payment'

    __name__ = 'loan.payment'

    loan = fields.Many2One('loan', 'Loan', ondelete='CASCADE')
    kind = fields.Selection([
            ('releasing_funds', 'Releasing Funds'),
            ('scheduled', 'Scheduled'),
            ('early', 'Early'),
            ('deffered', 'Deffered')], 'Kind')
    number = fields.Integer('Number')
    start_date = fields.Date('Date')
    begin_balance = fields.Function(
        fields.Numeric('Begin Balance',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_begin_balance')
    amount = fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    principal = fields.Numeric('Principal',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    interest = fields.Numeric('Interest',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    outstanding_balance = fields.Numeric('Outstanding Balance',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])

    @classmethod
    def __setup__(cls):
        super(LoanPayment, cls).__setup__()
        cls._order.insert(0, ('start_date', 'ASC'))

    @staticmethod
    def default_kind():
        return 'scheduled'

    def get_currency(self):
        return self.loan.currency

    def calculate(self, loan, at_date, number, begin_balance, increment):
        rate = loan.get_rate(increment.rate)
        self.amount = increment.payment_amount
        self.number = number
        self.start_date = at_date
        self.begin_balance = begin_balance
        self.interest = (loan.currency.round(begin_balance * rate)
            if rate else None)
        if getattr(increment, 'deferal', None):
            if increment.deferal == 'partially':
                self.principal = Decimal(0.0)
                self.interest = self.amount
            elif increment.deferal == 'fully':
                self.principal = (-self.interest
                    if self.interest else Decimal(0))
        else:
            if (self.begin_balance > self.amount
                    and number < loan.number_of_payments):
                self.principal = self.amount
                if self.interest:
                    self.principal -= self.interest
            else:
                self.principal = self.begin_balance
                if (getattr(self, 'principal', None)
                        and getattr(self, 'interest', None)):
                    self.amount = self.principal + self.interest
        self.outstanding_balance = self.begin_balance - self.principal

    def get_begin_balance(self, name=None):
        if self.outstanding_balance is not None and self.principal is not None:
            return self.outstanding_balance + self.principal


class LoanParty(model.CoopSQL):
    'Loan Party relation'

    __name__ = 'loan-party'

    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE')
    loan = fields.Many2One('loan', 'Loan', ondelete='CASCADE')

    def get_synthesis_rec_name(self, name):
        if self.loan:
            return self.loan.get_rec_name(name)
