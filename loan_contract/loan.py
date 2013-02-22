#-*- coding:utf-8 -*-
import copy
import math

from decimal import Decimal
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Or
from trytond.transaction import Transaction

from trytond.modules.coop_utils import utils, date

from trytond.modules.coop_utils import model
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

    __name__ = 'ins_contract.contract'
    __metaclass__ = PoolMeta

    is_loan_contract = fields.Function(
        fields.Boolean('Is Loan Contract', states={'invisible': True}),
        'get_is_loan_contract')
    loans = fields.One2Many('ins_contract.loan', 'contract', 'Loans',
        states={'invisible': ~Eval('is_loan_contract')},
        depends=['is_loan_contract'])

    def get_is_loan_contract(self, name=None):
        if not self.options and self.offered:
            return self.offered.get_is_loan_product()
        for option in self.options:
            if option.get_is_loan_option():
                return True
        return False

    def init_from_subscriber(self):
        loan = utils.instanciate_relation(self.__class__, 'loans')
        loan.init_from_contract(self)
        loan.init_from_borrowers([self.subscriber])
        if not hasattr(self, 'loan'):
            self.loans = []
        self.loans.append(loan)
        return True


class LoanOption():
    'Loan Option'

    __name__ = 'ins_contract.option'
    __metaclass__ = PoolMeta

    is_loan_option = fields.Function(
        fields.Boolean('Is Loan Option', states={'invisible': True}),
        'get_is_loan_option')

    def get_is_loan_option(self, name=None):
        return self.offered and self.offered.family == 'loan'


class Loan(model.CoopSQL, model.CoopView):
    'Loan'

    __name__ = 'ins_contract.loan'

    kind = fields.Selection(LOAN_KIND, 'Kind', sort=False)
    contract = fields.Many2One('ins_contract.contract', 'Contract',
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
        return self.amount

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
        self.first_payment_date = date.add_month(self.funds_release_date, 1)


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
        states={
            'invisible': ~Eval('_parent_option', {}).get('is_loan_option')},
        domain=[('person', '=', Eval('person'))],
        depends=['person'])
    person = fields.Function(
        fields.Many2One('party.party', 'Person'),
        'get_person')

    def get_person(self, name=None):
        if self.covered_element:
            return self.covered_element.person.id

    def init_from_option(self, option):
        super(LoanCoveredData, self).init_from_option(option)

    def init_from_covered_element(self, covered_element):
        super(LoanCoveredData, self).init_from_covered_element(covered_element)
        if not hasattr(self, 'loan_shares'):
            self.loan_shares = []
        for loan in self.option.contract.loans:
            for share in loan.loan_shares:
                if share.person.id == covered_element.person.id:
                    self.loan_shares.append(share)


class LoanCoveredDataLoanShareRelation(model.CoopSQL):
    'Loan Covered Data Loan Share Relation'

    __name__ = 'ins_contract.loan_covered_data-loan_share'

    covered_data = fields.Many2One('ins_contract.covered_data', 'Covered Data')
    loan_share = fields.Many2One('ins_contract.loan_share', 'Loan Share')
