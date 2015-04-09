import operator
from collections import OrderedDict
from itertools import groupby

from trytond.pool import Pool, PoolMeta
from trytond.wizard import Wizard, StateAction
from trytond.transaction import Transaction

__all__ = [
    'Contract',
    'DisplayContractSetPremium',
    'ContractSet',
    ]

__metaclass__ = PoolMeta


class Contract:
    __name__ = 'contract'

    @classmethod
    def calculate_prices(cls, contracts, start=None, end=None):
        new_contracts = []
        for contract in contracts:
            new_contracts += contract.contract_set.contracts \
                if contract.contract_set else [contract]
        new_contracts = list(set(new_contracts))
        return super(Contract, cls).calculate_prices(new_contracts,
            start, end)

    def appliable_fees(self):
        all_fees = super(Contract, self).appliable_fees()
        if self.contract_set:
            contract_ids = [contract.id for contract in
                self.contract_set.contracts]
            contract_ids.sort()
            if self.id == contract_ids[0]:
                return all_fees
            else:
                return set([fee for fee in all_fees if not fee.one_per_set])
        return all_fees


class DisplayContractSetPremium(Wizard):
    'Display Contract Set Premium'
    __name__ = 'contract.set.premium.display'

    start_state = 'display'
    display = StateAction('premium.act_premium_display')

    @classmethod
    def __setup__(cls):
        super(DisplayContractSetPremium, cls).__setup__()
        cls._error_messages.update({
                'no_contract_set_found': 'No contract set found in context',
                })

    def do_display(self, action):
        pool = Pool()
        ContractSet = pool.get('contract.set')
        if Transaction().context.get('active_model', '') != 'contract.set':
            self.raise_user_error('no_contract_set_found')
        contract_sets = ContractSet.browse(
            Transaction().context.get('active_ids'))

        contracts = []
        for contract_set in contract_sets:
            contracts.extend([contract.id
                    for contract in contract_set.contracts])
        return action, {
            'ids': contracts,
        }


class ContractSet:
    __name__ = 'contract.set'

    def invoice_contracts_till_next_renewal_date(self):
        for contract in self.contracts:
            contract.invoice_till_next_renewal_date()

    def contract_groups_info(self):

        def keyfunc(item):
            b = item.billing_information
            account = b.direct_debit_account if b.billing_mode.direct_debit \
                else None
            return ('billing_mode', b.billing_mode.name,
                    'account', account,
                    'end_date', item.end_date)

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
        end_date"""
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
