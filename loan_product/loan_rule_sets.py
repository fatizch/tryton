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
    def _re_get_loan_monthly_payment_number(cls, args):
        loan = args['loan']
        if hasattr(loan, 'monthly_payment_number'):
            return loan.monthly_payment_number

    @classmethod
    @check_args('loan')
    def _re_get_loan_monthly_payment_amount(cls, args):
        loan = args['loan']
        if hasattr(loan, 'monthly_payment_amount'):
            return loan.monthly_payment_number
