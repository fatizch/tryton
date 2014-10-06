import bisect
from decimal import Decimal

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval, Bool, Len, If

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
    ('interest_free', 'Interest Free Loan'),
    ('graduated', 'Graduated'),
    ('intermediate', 'Intermediate'),
    ('balloon', 'Balloon'),
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
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        ondelete='RESTRICT')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'),
        'on_change_with_currency_symbol')
    number_of_payments = fields.Function(
        fields.Integer('Number of Payments', required=True),
        'on_change_with_number_of_payments', 'setter_void')
    payment_frequency = fields.Selection(coop_date.DAILY_DURATION,
        'Payment Frequency', sort=False, required=True,
        domain=[('payment_frequency', 'in',
                ['month', 'quarter', 'half_year', 'year'])])
    amount = fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits', 'kind'],
        required=True)
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
    payments = fields.One2Many('loan.payment', 'loan', 'Payments',
        # We force the order to make sure bisect will work properly
        order=[('start_date', 'ASC')],
        states={'readonly': True})
    increments = fields.One2Many('loan.increment', 'loan', 'Increments',
        context={
            'payment_frequency': Eval('payment_frequency'),
            'start_date': Eval('first_payment_date'),
            'rate': Eval('rate'),
            'number': Len(Eval('increments', [])),
            },
        states={
            'readonly': Eval('kind') != 'graduated',
            },
        depends=['payment_frequency', 'rate', 'first_payment_date',
            'increments', 'number_of_payments', 'kind'])
    deferal = fields.Function(
        fields.Selection(DEFERALS, 'Deferal',
            states={
                'invisible': ~Eval('kind').in_(
                    ['fixed_rate', 'interest_free']),
                },
            depends=['kind']),
        'get_deferal', 'setter_void')
    deferal_duration = fields.Function(
        fields.Integer('Deferal Duration',
            states={
                'invisible': ~Eval('deferal') | ~Eval('kind').in_(
                    ['fixed_rate', 'interest_free']),
                'required': Bool(Eval('deferal', '')),
                },
            depends=['deferal', 'kind']),
        'get_deferal_duration', 'setter_void')
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
        cls._error_messages.update({
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

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_currency():
        if Transaction().context.get('company'):
            Company = Pool().get('company.company')
            company = Company(Transaction().context['company'])
            return company.currency.id

    @staticmethod
    def default_kind():
        return 'fixed_rate'

    @staticmethod
    def default_payment_frequency():
        return 'month'

    @staticmethod
    def default_deferal():
        return ''

    @classmethod
    def default_parties(cls):
        party = Transaction().context.get('party', None)
        return [party] if party else []

    @staticmethod
    def calculate_rate(annual_rate, payment_frequency):
        if not annual_rate:
            annual_rate = Decimal(0)
        coeff = coop_date.convert_frequency(payment_frequency, 'year')
        return annual_rate / Decimal(coeff)

    @staticmethod
    def calculate_payment_amount(annual_rate, number_of_payments, amount,
            currency, payment_frequency, deferal=None):
        if not number_of_payments:
            return
        rate = Loan.calculate_rate(annual_rate, payment_frequency)
        if not deferal:
            if rate:
                den = Decimal((1 - (1 + rate) ** (-number_of_payments)))
                res = amount * rate / den
            else:
                res = amount / Decimal(number_of_payments)
        elif deferal == 'partially':
            res = amount * rate
        elif deferal == 'fully':
            res = Decimal(0)
        return currency.round(res)

    def calculate_increments_and_payments(self):
        Payment = Pool().get('loan.payment')
        payments = [Payment(
                kind='releasing_funds',
                number=0,
                start_date=self.funds_release_date,
                outstanding_balance=self.amount,
                )]
        increments = []
        if self.kind == 'graduated':
            for increment in self.increments:
                increments.append(increment)
        elif (getattr(self, 'deferal', None)
                and getattr(self, 'deferal_duration', None)):
            increments = self.create_increments_from_deferal(
                self.deferal_duration, self.deferal)
        elif self.number_of_payments:
            increments = [self.create_increment(self.number_of_payments)]

        n = 0
        begin_balance = self.amount
        from_date = self.first_payment_date
        for i, increment in enumerate(increments, 1):
            increment.number = i
            increment.start_date = from_date
            increment.begin_balance = begin_balance
            if increment.begin_balance and not increment.payment_amount:
                increment.payment_amount = Loan.calculate_payment_amount(
                    increment.rate, increment.number_of_payments,
                    increment.begin_balance, self.currency,
                    self.payment_frequency, increment.deferal)
            if not increment.start_date or not begin_balance:
                continue
            for j in range(increment.number_of_payments):
                n += 1
                payment = Payment.create_payment(from_date, n,
                    begin_balance, increment, self.payment_frequency,
                    self.currency, self.number_of_payments)
                payments.append(payment)
                begin_balance = payment.outstanding_balance
                from_date = coop_date.add_duration(self.first_payment_date,
                    self.payment_frequency, n)
        return increments, payments

    def calculate(self):
        pool = Pool()
        Increment = pool.get('loan.increment')
        Payment = pool.get('loan.payment')
        previous_increments = getattr(self, 'increments', [])
        previous_payments = getattr(self, 'payments', [])
        increments, payments = self.calculate_increments_and_payments()
        self.increments, self.payments = increments, payments
        if self.kind != 'graduated':
            Increment.delete([x for x in previous_increments if x.id])
        Payment.delete([x for x in previous_payments if x.id])

    def create_increment(self, duration=None, payment_amount=None,
            deferal=None):
        Increment = Pool().get('loan.increment')
        return Increment(
            number_of_payments=duration,
            rate=self.rate,
            payment_amount=payment_amount,
            deferal=deferal,
            )

    def create_increments_from_deferal(self, duration=None, deferal=None):
        result = [self.create_increment(duration, deferal=deferal)]
        if deferal is None:
            return result
        result.append(
            self.create_increment(self.number_of_payments - duration))
        return result

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

    def get_end_date(self, name):
        return self.increments[-1].end_date if self.increments else None

    def get_deferal(self, name):
        if self.increments:
            return self.increments[0].deferal

    def get_deferal_duration(self, name):
        if self.deferal:
            return self.increments[0].number_of_payments

    def init_from_borrowers(self, parties):
        if hasattr(self, 'loan_shares') and self.loan_shares:
            return
        self.loan_shares = []
        LoanShare = Pool().get('loan.share')
        for party in parties:
            share = LoanShare()
            share.person = party
            self.loan_shares.append(share)

    def get_payment(self, at_date=None):
        if not at_date:
            at_date = utils.today()
        bisect_list = utils.ProxyListWithGetter(self.payments,
            lambda x: x.start_date)
        insert_idx = bisect.bisect_right(bisect_list, at_date)
        return self.payments[insert_idx - 1] if insert_idx else None

    def get_outstanding_loan_balance(self, name=None, at_date=None):
        payment = self.get_payment(at_date)
        return payment.outstanding_balance if payment else None

    def init_dict_for_rule_engine(self, current_dict):
        current_dict['loan'] = self

    def get_loan_share(self, party):
        for share in self.loan_shares:
            if share.person == party:
                return share

    def get_publishing_values(self):
        result = super(Loan, self).get_publishing_values()
        result['amount'] = self.amount
        result['start_date'] = self.funds_release_date
        result['number_payments'] = self.number_of_payments
        return result

    def get_payment_amount(self, at_date=None):
        at_date = at_date or utils.today()
        increment = utils.get_value_at_date(self.increments, at_date,
            'start_date')
        return increment.payment_amount if increment else None

    @fields.depends('kind', 'deferal', 'number_of_payments',
            'deferal_duration', 'increments', 'payments', 'rate',
            'first_payment_date', 'payment_frequency', 'currency', 'amount',
            'funds_release_date')
    def _on_change(self, name=None):
        changes = {}
        if self.kind in ['intermediate', 'balloon']:
            self.deferal = 'partially'
            self.deferal_duration = (self.number_of_payments - 1
                if self.number_of_payments else None)
        elif self.kind in ['interest_free', 'graduated']:
            self.deferal = None
            self.deferal_duration = None
            if self.kind == 'interest_free':
                self.rate = Decimal(0)
        changes['deferal'] = self.deferal
        changes['deferal_duration'] = self.deferal_duration
        changes['rate'] = self.rate

        if name and name in ['funds_release_date', 'payment_frequency']:
            if self.funds_release_date and self.payment_frequency:
                self.first_payment_date = coop_date.add_duration(
                    self.funds_release_date, self.payment_frequency)
            else:
                self.first_payment_date = None
        changes['first_payment_date'] = self.first_payment_date

        previous_increments = self.increments
        previous_payments = self.payments
        increments, payments = self.calculate_increments_and_payments()
        if increments and self.kind != 'graduated':
            changes['increments'] = {
                'add': [(-1, x._save_values) for x in increments],
                'remove': [x.id for x in previous_increments],
                }
        if payments:
            changes['payments'] = {
                'add': [(-1, x._save_values) for x in payments],
                'remove': [x.id for x in previous_payments],
                }
        return changes

    on_change_kind = _on_change
    on_change_number_of_payments = _on_change
    on_change_deferal = _on_change
    on_change_deferal_duration = _on_change
    on_change_rate = _on_change
    on_change_currency = _on_change
    on_change_amount = _on_change
    on_change_first_payment_date = _on_change

    @fields.depends('kind', 'deferal', 'number_of_payments',
        'deferal_duration', 'increments', 'payments', 'rate',
        'first_payment_date', 'payment_frequency', 'currency', 'amount',
        'funds_release_date')
    def on_change_funds_release_date(self):
        return self._on_change('funds_release_date')

    @fields.depends('kind', 'deferal', 'number_of_payments',
        'deferal_duration', 'increments', 'payments', 'rate',
        'first_payment_date', 'payment_frequency', 'currency', 'amount',
        'funds_release_date')
    def on_change_payment_frequency(self):
        return self._on_change('payment_frequency')

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        return self.currency.digits if self.currency else 2

    @fields.depends('currency')
    def on_change_with_currency_symbol(self, name=None):
        return self.currency.symbol if self.currency else ''

    @fields.depends('increments')
    def on_change_with_number_of_payments(self, name=None):
        return sum([x.number_of_payments for x in self.increments])

    @fields.depends('kind', 'deferal', 'number_of_payments',
        'deferal_duration', 'increments', 'payments', 'rate',
        'first_payment_date', 'payment_frequency', 'currency', 'amount',
        'funds_release_date')
    def on_change_increments(self):
        changes = {}
        previous_payments = self.payments
        increments, payments = self.calculate_increments_and_payments()
        if payments:
            to_update = []
            for increment in increments:
                cur_dict = increment._save_values
                cur_dict['id'] = increment.id
                to_update.append(cur_dict)
            changes['increments'] = {'update': to_update}
            changes['payments'] = {
                'add': [(-1, x._save_values) for x in payments],
                'remove': [x.id for x in previous_payments],
                }
        return changes


class LoanIncrement(model.CoopSQL, model.CoopView, ModelCurrency):
    'Loan Increment'

    __name__ = 'loan.increment'

    number = fields.Integer('Number')
    begin_balance = fields.Numeric('Begin Balance',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Function(
        fields.Date('End Date'),
        'on_change_with_end_date')
    loan = fields.Many2One('loan', 'Loan', ondelete='CASCADE', required=True)
    number_of_payments = fields.Integer('Number of Payments', required=True,
        domain=[('number_of_payments', '>', 0)])
    rate = fields.Numeric('Annual Rate', digits=(16, 4))
    payment_amount = fields.Numeric('Payment Amount',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'], required=True)
    deferal = fields.Selection(DEFERALS, 'Deferal', sort=False)

    @classmethod
    def __setup__(cls):
        super(LoanIncrement, cls).__setup__()
        cls._order.insert(0, ('number', 'ASC'))

    def pre_validate(self):
        super(LoanIncrement, self).pre_validate()

    def get_currency(self):
        return self.loan.currency

    @staticmethod
    def default_start_date():
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

    @fields.depends('start_date', 'loan', 'number_of_payments')
    def on_change_with_end_date(self, name=None):
        if self.number_of_payments and self.start_date and self.loan:
            return coop_date.add_duration(self.start_date,
                self.loan.payment_frequency, self.number_of_payments - 1)

    @fields.depends('loan', 'start_date', 'number_of_payments')
    def on_change_loan(self):
        return {'end_date': self.on_change_with_end_date()}


class LoanPayment(model.CoopSQL, model.CoopView, ModelCurrency):
    'Loan Payment'

    __name__ = 'loan.payment'

    loan = fields.Many2One('loan', 'Loan', ondelete='CASCADE', select=True,
        required=True)
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

    @classmethod
    def create_payment(cls, at_date, number, begin_balance, increment,
            payment_frequency, currency, total_number_of_payments):
        Payment = Pool().get('loan.payment')
        rate = Loan.calculate_rate(increment.rate, payment_frequency)
        payment = Payment(
            kind='scheduled',
            amount=increment.payment_amount,
            number=number,
            start_date=at_date,
            begin_balance=begin_balance,
            interest=(currency.round(begin_balance * rate) if rate else None),
            )
        if getattr(increment, 'deferal', None):
            if increment.deferal == 'partially':
                payment.principal = Decimal(0)
                payment.interest = payment.amount
            elif increment.deferal == 'fully':
                payment.principal = (-payment.interest
                    if payment.interest else Decimal(0))
        else:
            if (payment.begin_balance > payment.amount
                    and number < total_number_of_payments):
                payment.principal = payment.amount
                if payment.interest:
                    payment.principal -= payment.interest
            else:
                payment.principal = payment.begin_balance
                if (getattr(payment, 'principal', None)
                        and getattr(payment, 'interest', None)):
                    payment.amount = payment.principal + payment.interest
        payment.outstanding_balance = (payment.begin_balance
            - payment.principal)
        return payment

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
