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
