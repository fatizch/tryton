from decimal import Decimal
from collections import defaultdict
from sql import Literal
from sql.aggregate import Sum, Max
from sql.conditionals import Coalesce

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import coop_date


__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    ]


class Contract:
    __name__ = 'contract'

    @property
    def _premium_per_loan_cache(self):
        if hasattr(self, '__premium_per_loan_cache'):
            return self.__premium_per_loan_cache
        self.__premium_per_loan_cache = {}
        return self.__premium_per_loan_cache

    def _clear_premium_aggregates_cache(self):
        super(Contract, self)._clear_premium_aggregates_cache()
        self.__premium_per_loan_cache = {}

    def calculate_premium_per_loan(self):
        cached_values = self._premium_per_loan_cache.get(self.id, None)
        if cached_values:
            return cached_values
        cursor = Transaction().cursor
        pool = Pool()

        premium_amount = pool.get('contract.premium.amount').__table__()
        premium = pool.get('contract.premium').__table__()
        payment = pool.get('loan.payment').__table__()

        query_table = premium_amount.join(premium, condition=(
                premium_amount.premium == premium.id)
            ).join(payment, type_='LEFT OUTER', condition=(
                (payment.loan == premium.loan)
                & (payment.start_date >= premium_amount.period_start)
                & (payment.start_date <= premium_amount.period_end)))
        amount_col = Sum(Coalesce(premium_amount.amount, Literal(0))).as_(
            'amount')
        tax_col = Sum(Coalesce(premium_amount.tax_amount, Literal(0))).as_(
            'tax')
        payment_col = Max(Coalesce(payment.amount, Literal(0))).as_(
            'payment_amount')

        cursor.execute(*query_table.select(premium.loan, premium.fee,
                premium_amount.period_start, amount_col, tax_col,
                payment_col, where=(premium_amount.contract == self.id),
                group_by=[premium.loan, premium.fee,
                    premium_amount.period_start],
                order_by=premium_amount.period_start))

        premiums = {
            'per_period': cursor.dictfetchall(),
            'loan_totals': defaultdict(lambda: {
                    'amount': Decimal(0), 'tax': Decimal(0)}),
            'fee_totals': defaultdict(lambda: {
                    'amount': Decimal(0), 'tax': Decimal(0)}),
            }

        for data_dict in premiums['per_period']:
            if data_dict['loan']:
                data = premiums['loan_totals'][data_dict['loan']]
            elif data_dict['fee']:
                data = premiums['fee_totals'][data_dict['fee']]
            data['amount'] += data_dict['amount']
            data['tax'] += data_dict['tax']

        self._premium_per_loan_cache[self.id] = premiums
        return premiums

    def get_used_loans_ratios(self):
        loan_data = {loan.id: {
                'duration': coop_date.number_of_days_between(
                    loan.funds_release_date, loan.end_date),
                'max_insured': 0,
                } for loan in self.used_loans}
        for loan in self.used_loans:
            loan_data[loan.id]['max_insured'] = loan.amount * max(
                [share.share for share in loan.current_loan_shares])
        ratios = {}
        for loan_id, data in loan_data.iteritems():
            ratios[loan_id] = {
                'longest': data['duration'] == max(
                    [x['duration'] for x in loan_data.values()]),
                'biggest': data['max_insured'] == max(
                    [x['max_insured'] for x in loan_data.values()]),
                'prorata': data['max_insured'] / sum(
                    [x['max_insured'] for x in loan_data.values()]),
                }
        return ratios
