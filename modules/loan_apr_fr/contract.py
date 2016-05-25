from decimal import Decimal
from collections import defaultdict

from trytond.pool import PoolMeta
from trytond.cache import Cache

from trytond.modules.cog_utils import coop_date


__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    ]


class Contract:
    __name__ = 'contract'

    _premium_per_loan_cache = Cache('premiums_per_loan')

    def calculate_premium_per_loan(self):
        premiums = self.__class__._premium_per_loan_cache.get(self.id, None)
        if premiums is not None:
            return premiums
        futures = self.get_future_invoices(self)
        per_period = defaultdict(lambda: {'amount': 0, 'tax': 0})
        premiums = {
            'per_period': [],
            'loan_totals': defaultdict(lambda: {
                    'amount': Decimal(0), 'tax': Decimal(0)}),
            'fee_totals': defaultdict(lambda: {
                    'amount': Decimal(0), 'tax': Decimal(0)}),
            }

        for invoice in futures:
            for line in invoice['details']:
                premium = line['premium']
                data = per_period[(line['start'], premium.loan, premium.fee)]
                data['amount'] += line['amount']
                data['tax'] += line['tax_amount']
                specific_data = None
                if premium.loan:
                    specific_data = premiums['loan_totals'][premium.loan.id]
                elif premium.fee:
                    specific_data = premiums['fee_totals'][premium.fee.id]
                if specific_data is not None:
                    specific_data['amount'] += line['amount']
                    specific_data['tax'] += line['tax_amount']

        for (period_start, loan, fee), data in per_period.iteritems():
            premiums['per_period'].append({
                    'loan': loan.id if loan else None,
                    'fee': fee.id if fee else None,
                    'period_start': period_start,
                    'amount': data['amount'],
                    'tax': data['tax']})

        self.__class__._premium_per_loan_cache.set(self.id, premiums)
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
