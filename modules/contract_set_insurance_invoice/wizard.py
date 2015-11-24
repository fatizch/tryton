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
        for contract in contracts:
            if contract.contract_set:
                if not set(contract.contract_set.contracts).issubset(
                        contracts):
                    cls.raise_user_error('must_renew_all',
                        contract.contract_set.number)
        return super(Renew, cls).renew_contracts(contracts)
