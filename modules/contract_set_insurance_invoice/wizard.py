from trytond.pool import PoolMeta
from trytond.transaction import Transaction

__metaclass__ = PoolMeta
__all__ = [
    'Renew',
]


class Renew:
    __name__ = 'contract_term_renewal.renew'

    @classmethod
    def __setup__(cls):
        super(Renew, cls).__setup__()
        cls._error_messages.update({
                'must_renew_all': 'All contracts on contract set %s'
                ' must be renewed together',
                })

    @classmethod
    def renew_contracts(cls, contracts):
        renewed_contracts = super(Renew, cls).renew_contracts(contracts)
        contract_sets = []
        for contract in renewed_contracts:
            if contract.contract_set:
                if not set(contract.contract_set.contracts).issubset(
                        renewed_contracts):
                    cls.raise_user_error('must_renew_all',
                        contract.contract_set.number)
            if contract.contract_set and contract.contract_set not in \
                    contract_sets:
                contract_sets.append(contract.contract_set)
        for contract_set in contract_sets:
            new_start_date = \
                    contract_set.contracts[0].activation_history[-1].start_date
            with Transaction().set_context(
                    client_defined_date=new_start_date):
                contract_set.produce_reports([contract_set], 'renewal')
        return renewed_contracts
