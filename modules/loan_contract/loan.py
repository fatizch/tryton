#-*- coding:utf-8 -*-
import math

from decimal import Decimal
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
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
]


LOAN_KIND = [
    ('fixed_rate', 'Fixed Rate'),
    ('adjustable_rate', 'Adjustable Rate'),
    ('balloon', 'Balloon'),
    ('leasing', 'Leasing'),
    ('graduated', 'Graduated'),
    ('intermediate', 'Intermediate'),
    ('revolving', 'Revolving'),
    ('zero_interest', 'Zero Interest Loan'),
]


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


class LoanOption():
    'Loan Option'

    __name__ = 'contract.subscribed_option'
    __metaclass__ = PoolMeta

    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan')

    def get_is_loan(self, name=None):
        return self.offered and self.offered.family == 'loan'


class Loan(model.CoopSQL, model.CoopView):
    'Loan'

    __name__ = 'ins_contract.loan'

    kind = fields.Selection(LOAN_KIND, 'Kind', sort=False)
    contract = fields.Many2One('contract.contract', 'Contract',
        ondelete='CASCADE')
    monthly_payment_number = fields.Integer('Monthly Payment Number')
    monthly_payment_amount = fields.Numeric('Monthly Payment Amount',
        on_change_with=['monthly_payment_amount', 'kind', 'fixed_rate',
            'amount', 'monthly_payment_number'])
    amount = fields.Numeric('Amount')
    funds_release_date = fields.Date('Funds Release Date')
    first_payment_date = fields.Date('First Payment Date')
    loan_shares = fields.One2Many('ins_contract.loan_share',
        'loan', 'Loan Shares')
    outstanding_capital = fields.Numeric('Outstanding Capital')
    fixed_rate = fields.Numeric('Fixed Rate',
        states={'invisible': Eval('kind') != 'fixed_rate'})
    lender = fields.Many2One('party.party', 'Lender',
        domain=[('bank_role', '>', 0)])
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'get_currency_id')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'get_currency_digits')
    currency_symbol = fields.Function(
        fields.Char('Symbol'),
        'get_currency_symbol')

    @classmethod
    def default_kind(cls):
        return 'fixed_rate'

    def on_change_with_monthly_payment_amount(self):
        if not self.amount or not self.monthly_payment_number:
            return self.monthly_payment_amount
        if self.kind == 'fixed_rate' and self.fixed_rate:
            t = Decimal(self.fixed_rate / (100 * 12))
            num = Decimal(self.amount * t)
            den = Decimal((1 - math.pow(1 + t, -self.monthly_payment_number)))
            return num / den
        return self.monthly_payment_amount

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

    def get_currency_digits(self, name):
        if hasattr(self, 'currency') and self.currency:
            return self.currency.digits

    @staticmethod
    def default_currency():
        return Transaction().context.get('currency')

    def get_currency_id(self, name):
        currency = self.get_currency()
        if currency:
            return currency.id

    def get_currency(self):
        if hasattr(self, 'contract') and self.contract:
            return self.contract.get_currency()

    @staticmethod
    def default_currency_symbol():
        Currency = Pool().get('currency.currency')
        currency = Currency(Transaction().context.get('currency'))
        if currency and hasattr(currency, 'symbol'):
            return currency.symbol
        return ''

    def get_currency_symbol(self, name):
        if hasattr(self, 'currency') and self.currency:
            return self.currency.symbol
        return ''


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

    def init_from_covered_element(self, covered_element):
        super(LoanCoveredData, self).init_from_covered_element(covered_element)
        if not hasattr(self, 'loan_shares'):
            self.loan_shares = []
        for loan in self.option.contract.loans:
            for share in loan.loan_shares:
                if share.person.id == covered_element.party.id:
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
