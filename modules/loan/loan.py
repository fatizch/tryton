from decimal import Decimal
from sql.aggregate import Max

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.cog_utils import utils, coop_date, fields, model
from trytond.modules.currency_cog import ModelCurrency

__all__ = [
    'Loan',
    'ContractLoanRelation',
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


class Loan(model.CoopSQL, model.CoopView, ModelCurrency):
    'Loan'

    __name__ = 'loan'

    kind = fields.Selection(LOAN_KIND, 'Kind', sort=False)
    contracts = fields.Many2Many('contract-loan', 'loan', 'contract',
        'Contracts')
    number_of_payments = fields.Integer('Number of Payments')
    payment_frequency = fields.Selection(coop_date.DAILY_DURATION,
        'Payment Frequency', sort=False)
    payment_amount = fields.Numeric('Payment Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'],
        on_change_with=['payment_amount', 'kind', 'rate',
            'amount', 'number_of_payments', 'currency', 'payment_frequency',
            'first_payment_date', 'increments'])
    amount = fields.Numeric('Amount')
    funds_release_date = fields.Date('Funds Release Date')
    first_payment_date = fields.Date('First Payment Date')
    loan_shares = fields.One2Many('loan.share', 'loan', 'Loan Shares')
    outstanding_capital = fields.Numeric('Outstanding Capital')
    rate = fields.Numeric('Annual Rate', digits=(16, 4), states={
            'invisible': ~Eval('kind').in_(['fixed_rate', 'intermediate'])})
    lender = fields.Many2One('bank', 'Lender')
    payments = fields.One2Many('loan.payment', 'loan',
        'Payments')
    early_payments = fields.One2ManyDomain('loan.payment', 'loan',
        'Early Payments', domain=[('kind', '=', 'early')])
    increments = fields.One2Many('loan.increment', 'loan', 'Increments')
    defferal = fields.Function(
        fields.Selection(DEFFERALS, 'Differal'),
        'get_defferal')
    defferal_duration = fields.Function(
        fields.Integer('Differal Duration'),
        'get_defferal_duration')
    end_date = fields.Function(
        fields.Date('End Date'),
        'get_loan_end_date')

    @classmethod
    def __setup__(cls):
        super(Loan, cls).__setup__()
        cls._buttons.update({
                'calculate_amortization_table': {},
                })

        utils.update_selection(cls, 'payment_frequency',
            keys_to_remove=['day'])

    @classmethod
    def default_kind(cls):
        return 'fixed_rate'

    def on_change_with_payment_amount(self):
        if (not self.amount or not self.number_of_payments
                or not self.first_payment_date):
            return self.payment_amount
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
        self.first_payment_date = coop_date.add_month(
            self.funds_release_date, 1)

    def get_currency(self):
        if hasattr(self, 'contracts') and self.contracts:
            return self.contracts[0].currency

    def get_currency_id(self, name):
        if 'currency' in Transaction().context:
            return Transaction().context.get('currency')
        else:
            return super(Loan, self).get_currency_id(name)

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
        while begin_balance > 0:
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

    @classmethod
    @model.CoopView.button
    def calculate_amortization_table(cls, loans):
        Payment = Pool().get('loan.payment')
        for loan in loans:
            if loan.payments:
                Payment.delete(
                    [x for x in loan.payments if x.kind == 'scheduled'])
            loan.payments = list(loan.payments)
            loan.payments[:] = [x for x in loan.payments
                if x.kind != 'scheduled']
            loan.payments += loan.calculate_payments()
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
        return [x for x in self.early_payments
            if x.start_date >= at_date and x.start_date <= to_date]

    def update_increments(self):
        start_date = self.first_payment_date
        i = 0
        deffered_payments = 0
        for increment in self.increments:
            i += 1
            increment.number = i
            increment.start_date = start_date
            if not utils.is_none(increment, 'number_of_payments'):
                increment.end_date = coop_date.get_end_of_period(start_date,
                    self.payment_frequency, increment.number_of_payments)
            defferal = (increment.defferal
                if hasattr(increment, 'defferal') else None)
            if not utils.is_none(increment, 'rate'):
                increment.payment_amount = self.calculate_payment_amount(
                    increment.rate,
                    self.number_of_payments - deffered_payments,
                    self.amount, defferal)
            if defferal:
                deffered_payments += increment.number_of_payments
            if not utils.is_none(increment, 'number_of_payments'):
                start_date = coop_date.add_day(increment.end_date, 1)

    def create_increments_from_defferal(self, defferal, duration):
        Increment = Pool().get('loan.increment')
        increment_1 = Increment()
        increment_1.defferal = defferal
        increment_1.number_of_payments = duration
        increment_1.rate = self.rate
        increment_2 = Increment()
        increment_2.number_of_payments = self.number_of_payments - duration
        increment_2.rate = self.rate
        return [increment_1, increment_2]

    def calculate_increments(self, defferal=None, defferal_duration=None):
        increments = []
        if defferal and defferal_duration:
            increments = self.create_increments_from_defferal(defferal,
                defferal_duration)
        elif self.kind == 'intermediate':
            increments = self.create_increments_from_defferal('partially',
                self.number_of_payments - 1)
        elif self.kind == 'graduated':
            Increment = Pool().get('loan.increment')
            increment = Increment()
            increment.start_date = self.funds_release_date
            increments = [increment]
        if not hasattr(self, 'increments'):
            self.increments = []
        self.increments = list(self.increments)
        self.increments += increments
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
    def get_loan_end_date(cls, loans):
        pool = Pool()
        cursor = Transaction().cursor
        loan = pool.get('loan').__table__()
        increment = pool.get('loan.increment').__table__()
        query_table = loan.join(increment, type_='LEFT',
            condition=(loan.id == increment.loan))
        cursor.execute(*query_table.select(loan.id, Max(increment.end_date),
                group_by=loan.id))
        return dict(cursor.fetchall())


class ContractLoanRelation(model.CoopSQL, model.CoopView):
    'Contract Loan Relation'

    __name__ = 'contract-loan'

    loan_number = fields.Integer('Loan Number')
    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE')
    loan = fields.Many2One('loan', 'Loan', ondelete='RESTRICT')


class LoanShare(model.CoopSQL, model.CoopView):
    'Loan Share'

    __name__ = 'loan.share'
    _rec_name = 'share'

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


class LoanIncrement(model.CoopSQL, model.CoopView, ModelCurrency):
    'Loan Increment'

    __name__ = 'loan.increment'

    number = fields.Integer('Number', readonly=True)
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date', on_change_with=['loan', 'start_date',
            'number_of_payments'])
    loan = fields.Many2One('loan', 'Loan', ondelete='CASCADE')
    number_of_payments = fields.Integer('Number of Payments')
    rate = fields.Numeric('Annual Rate', digits=(16, 4))
    payment_amount = fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    defferal = fields.Selection(DEFFERALS, 'Differal', sort=False)

    @classmethod
    def __setup__(cls):
        super(LoanIncrement, cls).__setup__()
        cls._order.insert(0, ('number', 'ASC'))

    def get_currency(self):
        return self.loan.currency

    def on_change_with_end_date(self):
        return coop_date.add_duration(self.start_date, self.number_of_payments,
            self.loan.payment_frequency)


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
    insurance = fields.Numeric('Insurance',
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
            increment=None, early_payments=None):
        rate = loan.get_rate(increment.rate if increment else loan.rate,)
        payment_amount = (increment.payment_amount
            if increment else loan.payment_amount)
        self.loan = loan
        self.number = number
        self.start_date = at_date
        self.end_date = end_date
        self.begin_balance = begin_balance
        if early_payments:
            self.begin_balance -= sum(map(lambda x: x.amount, early_payments))
        self.interest = self.loan.currency.round(begin_balance * rate)
        if increment and not utils.is_none(increment, 'defferal'):
            if increment.defferal == 'partially':
                self.principal = 0
                self.interest = payment_amount
            elif increment.defferal == 'fully':
                self.principal = -self.interest
        else:
            if (self.begin_balance > payment_amount
                    and number < self.loan.number_of_payments):
                self.principal = payment_amount - self.interest
            else:
                self.principal = self.begin_balance
        self.amount = self.principal + self.interest
        self.end_balance = self.get_end_balance()

    def get_end_balance(self, name=None):
        if self.begin_balance is not None and self.principal is not None:
            return self.begin_balance - self.principal
