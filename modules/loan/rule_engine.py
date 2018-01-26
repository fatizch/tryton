# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args
from .loan import Loan

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('loan')
    def _re_get_loan_kind(cls, args):
        loan = args['loan']
        if hasattr(loan, 'kind'):
            return loan.kind

    @classmethod
    @check_args('loan')
    def _re_get_loan_duration(cls, args):
        loan = args['loan']
        if hasattr(loan, 'duration'):
            return loan.duration

    @classmethod
    @check_args('loan')
    def _re_get_loan_payment_amount(cls, args, date=None):
        if not date:
            date = args['date']
        loan = args['loan']
        return loan.get_payment_amount(date)

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
    def _re_get_outstanding_loan_balance(cls, args, date=None):
        if not date:
            date = args['date']
        return args['loan'].get_outstanding_loan_balance(at_date=date)

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

    @classmethod
    @check_args('loan')
    def _re_get_early_repayments_amount(cls, args, date=None):
        if not date:
            date = args['date']
        loan = args['loan']
        return loan.get_early_repayments_amount(date)

    @classmethod
    @check_args('option')
    def _re_get_insured_outstanding_loan_balance(cls, args, date=None):
        if not date:
            date = args['date']
        option = args['option']
        return option.get_insured_outstanding_loan_balance(date)

    @classmethod
    @check_args('option')
    def _re_get_option_loan_balance(cls, args, date=None):
        if not date:
            date = args['date']
        option = args['option']
        return option.get_option_loan_balance(date)

    @classmethod
    @check_args('option')
    def _re_get_total_loan_balance(cls, args, date=None):
        if not date:
            date = args['date']
        option = args['option']
        return option.get_total_loan_balance(date)
