from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coop_utils import utils, fields, model

__metaclass__ = PoolMeta
__all__ = [
    'LoanContract',
    'LoanOption',
    'LoanCoveredData',
    'LoanCoveredDataLoanShareRelation',
    ]


class LoanContract():
    'Loan Contract'

    __name__ = 'contract'

    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan')
    loans = fields.One2Many('loan.loan', 'contract', 'Loans',
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

    def init_dict_for_rule_engine(self, cur_dict):
        super(LoanContract, self).init_dict_for_rule_engine(cur_dict)
        #TODO : To enhance
        if not utils.is_none(self, 'loans'):
            cur_dict['loan'] = self.loans[-1]

    def get_dates(self):
        if not self.is_loan:
            return super(LoanContract, self).get_dates()
        result = set()
        for loan in self.loans:
            for payment in loan.payments:
                result.add(payment.start_date)
        return result

    @classmethod
    @model.CoopView.button_action('loan.launch_loan_creation_wizard')
    def create_loan(cls, loans):
        pass


class LoanOption():
    'Loan Option'

    __name__ = 'contract.option'

    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan')

    def get_is_loan(self, name=None):
        return self.offered and self.offered.family == 'loan'


class LoanCoveredData():
    'Loan Covered Data'

    __name__ = 'contract.covered_data'

    loan_shares = fields.Many2Many(
        'loan.covered_data-loan_share',
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

    __name__ = 'loan.covered_data-loan_share'

    covered_data = fields.Many2One('contract.covered_data', 'Covered Data',
        ondelete='CASCADE')
    loan_share = fields.Many2One('loan.share', 'Loan Share',
        ondelete='RESTRICT')
