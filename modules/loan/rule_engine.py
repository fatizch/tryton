from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args
from .loan import Loan

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

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
        return loan.get_payment_amount(args['date'])

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

    @classmethod
    @check_args('loan')
    def _re_get_outstanding_loan_balance(cls, args):
        return args['loan'].get_outstanding_loan_balance(at_date=args['date'])

    @classmethod
    @check_args('share')
    def _re_get_loan_share(cls, args):
        share = args['share']
        return share.share

    @classmethod
    @check_args('loan')
    def _re_get_periodic_rate_from_annual_rate(cls, args, rate=1):
        return Loan.calculate_rate(rate, args['loan'].payment_frequency)

    @classmethod
    def _re_get_loan(cls, args):
        return args['loan']

    @classmethod
    @check_args('loan')
    def _re_get_loan_payment_frequency(cls, args):
        return args['loan'].payment_frequency
