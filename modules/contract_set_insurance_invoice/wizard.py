# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

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
                active_contracts = [c for c in contract.contract_set.contracts
                    if c.status in ['active', 'hold'] and c.activation_history
                    and not c.activation_history[-1].final_renewal]
                if not set(active_contracts).issubset(
                        contracts):
                    cls.raise_user_error('must_renew_all',
                        contract.contract_set.number)
        return super(Renew, cls).renew_contracts(contracts)
