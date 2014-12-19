import operator
from collections import OrderedDict
from itertools import groupby

from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'ContractSet',
    ]


class ContractSet:

    __name__ = 'contract.set'

    def contract_groups_info(self):

        def keyfunc(item):
            b = item.billing_information
            account = b.direct_debit_account if b.billing_mode.direct_debit \
                else None
            return ('billing_mode', b.billing_mode.name,
                    'account', account,
                    'renewal_date', item.next_renewal_date)

        contracts = sorted(list(self.contracts), key=keyfunc)

        groups = []
        for key, contracts in groupby(contracts, key=keyfunc):
            groups.append(list(contracts))

        aggregated_invoices = []
        for group in groups:
            aggregated_invoices.append(self.aggregate_invoices_reports(group))

        return aggregated_invoices

    def aggregate_invoices_reports(self, contract_group):
        """Contract groups passed to this function should be
        grouped by billing_mode, direct_debit_account, and
        next_renewal_date"""
        aggregated = {}
        raw_reports = [x.invoices_report()[0] for x in contract_group]
        bill_info = contract_group[0].billing_information
        if bill_info.billing_mode.direct_debit:
            aggregated['direct_debit'] = True
            aggregated['debit_account'] = bill_info.direct_debit_account.number
        else:
            aggregated['direct_debit'] = False

        tmp_aggregated = {}
        for report in raw_reports:
            for invoice in report:
                date = invoice['planned_payment_date']
                if date in tmp_aggregated:
                    tmp_aggregated[date]['total_amount'] += \
                        invoice['total_amount']
                    tmp_aggregated[date]['base_invoices'].append(invoice)
                else:
                    tmp_aggregated[date] = dict(invoice)
                    tmp_aggregated[date]['base_invoices'] = [invoice]

        ordered = OrderedDict(sorted(tmp_aggregated.items(),
                key=operator.itemgetter(0)))

        aggregated['invoices'] = ordered.values()
        aggregated['total'] = sum(
            [x['total_amount'] for x in aggregated['invoices']])
        aggregated['billing_mode'] = bill_info.billing_mode.name

        return aggregated
