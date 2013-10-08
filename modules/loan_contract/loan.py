from decimal import Decimal
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.wizard import StateTransition, StateView, Button
from trytond.transaction import Transaction

from trytond.modules.coop_utils import utils, coop_date, fields, model
from trytond.modules.coop_utils import coop_string

__all__ = [
    'LoanContract',
    'LoanOption',
    'Loan',
    'LoanShare',
    'LoanCoveredElement',
    'LoanCoveredData',
    'LoanCoveredDataLoanShareRelation',
    'LoanIncrement',
    'LoanPayment',
    'LoanParameters',
    'LoanIncrementsDisplayer',
    'AmortizationTableDisplayer',
    'LoanCreation',
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

STATES = {'required': ~~Eval('active')}
DEPENDS = ['active']


class LoanContract():
    'Loan Contract'

    __name__ = 'contract.contract'
    __metaclass__ = PoolMeta

    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan')
    loans = fields.One2Many('ins_contract.loan', 'contract', 'Loans',
        states={'invisible': ~Eval('is_loan')},
        depends=['is_loan', 'currency'],
        context={'currency': Eval('currency')})

    @classmethod
    def __setup__(cls):
        super(LoanContract, cls).__setup__()
        cls._buttons.update({'create_loan': {}})

    def get_is_loan(self, name):
        if not self.options and self.offered:
            return self.offered.is_loan
        for option in self.options:
            if option.is_loan:
                return True
        return False

    def init_from_subscriber(self):
        if not utils.is_none(self, 'loans'):
            return True
        loan = utils.instanciate_relation(self, 'loans')
        loan.init_from_contract(self)
        loan.init_from_borrowers([self.subscriber])
        if not hasattr(self, 'loan'):
            self.loans = []
        self.loans.append(loan)
        return True

    def init_dict_for_rule_engine(self, cur_dict):
        super(LoanContract, self).init_dict_for_rule_engine(cur_dict)
        #TODO : To enhance
        if not utils.is_none(self, 'loans'):
            cur_dict['loan'] = self.loans[-1]

    @classmethod
    @model.CoopView.button_action('loan_contract.launch_loan_creation_wizard')
    def create_loan(cls, loans):
        pass


class LoanOption():
    'Loan Option'

    __name__ = 'contract.subscribed_option'
    __metaclass__ = PoolMeta

    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan')

    def get_is_loan(self, name=None):
        return self.offered and self.offered.family == 'loan'


class Loan(model.CoopSQL, model.CoopView, model.ModelCurrency):
    'Loan'

    __name__ = 'ins_contract.loan'

    active = fields.Boolean('Active')
    kind = fields.Selection(LOAN_KIND, 'Kind', sort=False, states=STATES,
        depends=DEPENDS)
    contract = fields.Many2One('contract.contract', 'Contract',
        ondelete='CASCADE')
    number_of_payments = fields.Integer('Number of Payments', states=STATES,
        depends=DEPENDS)
    payment_frequency = fields.Selection(coop_date.DAILY_DURATION,
        'Payment Frequency', sort=False, states=STATES, depends=DEPENDS)
    payment_amount = fields.Numeric('Payment Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'],
        on_change_with=['payment_amount', 'kind', 'rate',
            'amount', 'number_of_payments', 'currency', 'payment_frequency',
            'first_payment_date', 'increments'])
    amount = fields.Numeric('Amount', states=STATES, depends=DEPENDS)
    funds_release_date = fields.Date('Funds Release Date')
    first_payment_date = fields.Date('First Payment Date', states=STATES,
        depends=DEPENDS)
    loan_shares = fields.One2Many('ins_contract.loan_share',
        'loan', 'Loan Shares')
    outstanding_capital = fields.Numeric('Outstanding Capital')
    rate = fields.Numeric('Annual Rate', states={
            'invisible': ~Eval('kind').in_(['fixed_rate', 'intermediate'])})
    lender = fields.Many2One('bank', 'Lender')
    payments = fields.One2Many('ins_contract.loan_payment', 'loan',
        'Payments')
    early_payments = fields.One2ManyDomain('ins_contract.loan_payment', 'loan',
        'Payments', domain=[('kind', '=', 'early')])
    increments = fields.One2Many('ins_contract.loan_increment', 'loan',
        'Increments')
    defferal = fields.Function(
        fields.Selection(DEFFERALS, 'Differal'),
        'get_defferal')
    defferal_duration = fields.Function(
        fields.Integer('Differal Duration'),
        'get_defferal_duration')

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
            res = coop_string.amount_as_string(self.amount, self.currency)
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
        if hasattr(self, 'contract') and self.contract:
            return self.contract.currency

    def get_rate(self, annual_rate=None):
        if not annual_rate:
            annual_rate = self.rate
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
        Payment = Pool().get('ins_contract.loan_payment')
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
        Payment = Pool().get('ins_contract.loan_payment')
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
            increment.end_date = coop_date.get_end_of_period(start_date,
                self.payment_frequency, increment.number_of_payments)
            defferal = (increment.defferal
                if hasattr(increment, 'defferal') else None)
            increment.amount = self.calculate_payment_amount(increment.rate,
                self.number_of_payments - deffered_payments, self.amount,
                defferal)
            if defferal:
                deffered_payments += increment.number_of_payments
            start_date = coop_date.add_day(increment.end_date, 1)

    def create_increments_from_defferal(self, defferal, duration):
        Increment = Pool().get('ins_contract.loan_increment')
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
        if not hasattr(self, 'increments'):
            self.increments = []
        self.increments = list(self.increments)
        self.increments += increments
        self.update_increments()


class LoanShare(model.CoopSQL, model.CoopView):
    'Loan Share'

    __name__ = 'ins_contract.loan_share'
    _rec_name = 'share'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    loan = fields.Many2One('ins_contract.loan', 'Loan', ondelete='CASCADE')
    share = fields.Numeric('Loan Share')
    person = fields.Many2One('party.party', 'Person', ondelete='RESTRICT',
        domain=[('is_person', '=', True)])

    @staticmethod
    def default_share():
        return 100


class LoanCoveredElement():
    'Borrower'

    __name__ = 'ins_contract.covered_element'
    __metaclass__ = PoolMeta


class LoanCoveredData():
    'Loan Covered Data'

    __name__ = 'ins_contract.covered_data'
    __metaclass__ = PoolMeta

    loan_shares = fields.Many2Many(
        'ins_contract.loan_covered_data-loan_share',
        'covered_data', 'loan_share', 'Loan Shares',
        states={'invisible': ~Eval('is_loan')},
        domain=[
            ('person', '=', Eval('person')),
            ('loan.contract', '=', Eval('contract'))],
        depends=['person', 'contract'])
    person = fields.Function(
        fields.Many2One('party.party', 'Person'),
        'get_person')
    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan')

    def get_person(self, name=None):
        if self.covered_element and self.covered_element.party:
            return self.covered_element.party.id

    def init_from_option(self, option):
        super(LoanCoveredData, self).init_from_option(option)
        if not hasattr(self, 'loan_shares'):
            self.loan_shares = []
        for loan in option.contract.loans:
            for share in loan.loan_shares:
                if share.person.id == self.covered_element.party.id:
                    self.loan_shares.append(share)

    def get_is_loan(self, name):
        return self.option and self.option.is_loan


class LoanCoveredDataLoanShareRelation(model.CoopSQL):
    'Loan Covered Data Loan Share Relation'

    __name__ = 'ins_contract.loan_covered_data-loan_share'

    covered_data = fields.Many2One('ins_contract.covered_data', 'Covered Data',
        ondelete='CASCADE')
    loan_share = fields.Many2One('ins_contract.loan_share', 'Loan Share',
        ondelete='RESTRICT')


class LoanIncrement(model.CoopSQL, model.CoopView, model.ModelCurrency):
    'Loan Increment'

    __name__ = 'ins_contract.loan_increment'

    number = fields.Integer('Number')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    loan = fields.Many2One('ins_contract.loan', 'Loan', ondelete='CASCADE')
    number_of_payments = fields.Integer('Number of Payments')
    rate = fields.Numeric('Annual Rate')
    payment_amount = fields.Numeric('Amount',
        digits=(16, Eval('currency_digts', 2)), depends=['currency_digits'])
    defferal = fields.Selection(DEFFERALS, 'Differal', sort=False)

    @classmethod
    def __setup__(cls):
        super(LoanIncrement, cls).__setup__()
        cls._order.insert(0, ('number', 'ASC'))

    def get_currency(self):
        return self.loan.currency


class LoanPayment(model.CoopSQL, model.CoopView, model.ModelCurrency):
    'Loan Payment'

    __name__ = 'ins_contract.loan_payment'

    loan = fields.Many2One('ins_contract.loan', 'Loan', ondelete='CASCADE')
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
        if increment and increment.defferal:
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
        return self.begin_balance - self.principal


class LoanParameters(model.CoopView, model.ModelCurrency):
    'Loan Parameters'

    __name__ = 'ins_contract.loan_creation_parameters'

    contract = fields.Many2One('contract.contract', 'Contract',
        states={"invisible": True})
    loan = fields.Many2One('ins_contract.loan', 'Loan')
    kind = fields.Selection(LOAN_KIND, 'Kind', required=True)
    number_of_payments = fields.Integer('Number of Payments', required=True)
    payment_frequency = fields.Selection(coop_date.DAILY_DURATION,
        'Payment Frequency', required=True, sort=False)
    amount = fields.Numeric('Amount', required=True)
    funds_release_date = fields.Date('Funds Release Date', required=True)
    first_payment_date = fields.Date('First Payment Date', required=True)
    rate = fields.Numeric('Annual Rate', required=True)
    lender = fields.Many2One('bank', 'Lender', required=True)
    defferal = fields.Selection(DEFFERALS, 'Differal', sort=False)
    defferal_duration = fields.Integer('Differal Duration')


class LoanIncrementsDisplayer(model.CoopView):
    'Increments'

    __name__ = 'ins_contract.loan_creation_increments'

    increments = fields.One2Many('ins_contract.loan_increment', None,
        'Increments')


class AmortizationTableDisplayer(model.CoopView):
    'Amortization Table'

    __name__ = 'ins_contract.loan_creation_table'

    payments = fields.One2Many('ins_contract.loan_payment', None, 'Payments')


class LoanCreation(model.CoopWizard):
    'Loan Creation'

    __name__ = 'ins_contract.loan_creation'

    start_state = 'loan_parameters'
    loan_parameters = StateView('ins_contract.loan_creation_parameters',
        'loan_contract.loan_creation_parameters_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'create_loan', 'tryton-go-next'),
            ])
    create_loan = StateTransition()
    increments = StateView('ins_contract.loan_creation_increments',
        'loan_contract.loan_creation_increments_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Previous', 'loan_parameters', 'tryton-go-previous'),
            Button('Next', 'create_payments', 'tryton-go-next',
                default=True),
            ])
    create_payments = StateTransition()
    amortization_table = StateView('ins_contract.loan_creation_table',
        'loan_contract.loan_creation_table_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Previous', 'increments', 'tryton-go-previous'),
            Button('End', 'validate_loan', 'tryton-go-next',
                default=True),
            ])
    validate_loan = StateTransition()

    def default_loan_parameters(self, values):
        Contract = Pool().get('contract.contract')
        contract = Contract(Transaction().context.get('active_id'))
        return {
            'contract': contract.id,
            'currency': contract.currency.id,
            'currency_symbol': contract.currency.symbol,
            'kind': 'fixed_rate',
            'payment_frequency': 'month',
            'funds_release_date': contract.start_date,
            }

    def default_increments(self, values):
        return {'increments':
            [x.id for x in self.loan_parameters.loan.increments]}

    def transition_create_loan(self):
        Loan = Pool().get('ins_contract.loan')
        loan = Loan()
        self.loan_parameters.loan = loan
        contract = self.loan_parameters.contract
        contract.loans = list(contract.loans)
        contract.loans.append(loan)
        loan.kind = self.loan_parameters.kind
        loan.payment_frequency = self.loan_parameters.payment_frequency
        loan.number_of_payments = self.loan_parameters.number_of_payments
        loan.amount = self.loan_parameters.amount
        loan.funds_release_date = self.loan_parameters.funds_release_date
        loan.rate = self.loan_parameters.rate
        loan.lender = self.loan_parameters.lender
        loan.first_payment_date = self.loan_parameters.first_payment_date
        loan.currency = contract.currency
        loan.payment_amount = loan.on_change_with_payment_amount()
        if (self.loan_parameters.defferal
                and self.loan_parameters.defferal_duration):
            loan.calculate_increments(defferal=self.loan_parameters.defferal,
                defferal_duration=self.loan_parameters.defferal_duration)
        loan.save()
        contract.save()
        if loan.kind != 'graduated' and not loan.increments:
            return 'create_payments'
        return 'increments'

    def default_amortization_table(self, values):
        return {'payments': [x.id for x in self.loan_parameters.loan.payments]}

    def transition_create_payments(self):
        if hasattr(self.increments, 'increments'):
            for increment in self.increments.increments:
                increment.save()
        self.loan_parameters.loan.calculate_amortization_table(
            [self.loan_parameters.loan])
        return 'amortization_table'

    def transition_validate_loan(self):
        contract = self.loan_parameters.contract
        if not contract.loans:
            contract.loans = []
        contract.loans = list(contract.loans)
        contract.loans.append(self.loan_parameters.loan)
        contract.save()
        return 'end'
