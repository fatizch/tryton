from trytond.modules.rule_engine import RuleEngineContext
from trytond.modules.rule_engine import InternalRuleEngineError
from trytond.modules.rule_engine import check_args
from trytond.modules.rule_engine import RuleTools

from trytond.modules.coop_utils import utils


class LoanContext(RuleEngineContext):
    '''
        Context functions for Loans.
    '''
    __name__ = 'ins_product.rule_sets.loan'

    @classmethod
    @check_args('loan')
    def _re_get_loan_kind(cls, args):
        loan = args['loan']
        if hasattr(loan, 'kind'):
            return loan.kind

    @classmethod
    @check_args('loan')
    def _re_get_loan_number_of_payments(cls, args):
        loan = args['loan']
        if hasattr(loan, 'number_of_payments'):
            return loan.number_of_payments

    @classmethod
    @check_args('loan')
    def _re_get_loan_payment_amount(cls, args):
        loan = args['loan']
        if hasattr(loan, 'payment_amount'):
            return loan.payment_amount

    @classmethod
    @check_args('loan')
    def _re_get_loan_amount(cls, args):
        loan = args['loan']
        if hasattr(loan, 'amount'):
            return loan.amount

    @classmethod
    @check_args('loan')
    def _re_get_loan_funds_release_date(cls, args):
        loan = args['loan']
        if hasattr(loan, 'funds_release_date'):
            return loan.funds_release_date

    @classmethod
    @check_args('loan')
    def _re_get_loan_first_payment_date(cls, args):
        loan = args['loan']
        if hasattr(loan, 'first_payment_date'):
            return loan.first_payment_date
