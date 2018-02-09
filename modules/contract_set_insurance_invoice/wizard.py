# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta


__all__ = [
    'Renew',
]


class Renew:
    __metaclass__ = PoolMeta
    __name__ = 'contract_term_renewal.renew'

    @classmethod
    def __setup__(cls):
        super(Renew, cls).__setup__()
        cls._error_messages.update({
                'must_renew_all': 'All contracts on contract set %s'
                ' must be renewed together',
                'should_renew_all': 'All contracts on contract set %s'
                ' should be renewed together, ensure you want to perform'
                ' this action',
                })

    @classmethod
    def renew_contracts(cls, contracts):
        for contract in contracts:
            if contract.contract_set:
                active_contracts = [c for c in contract.contract_set.contracts
                    if c.status in ['active', 'hold'] and c.activation_history
                    and not c.activation_history[-1].final_renewal]
                max_end_date = max([x.end_date or datetime.date.min
                        for x in active_contracts])
                if not set(active_contracts).issubset(
                        contracts):
                    if contract.end_date >= max_end_date:
                        cls.raise_user_error('must_renew_all',
                            contract.contract_set.number)
                    cls.raise_user_warning('should_renew_all_%s' %
                        contract.contract_set.number, 'should_renew_all',
                        contract.contract_set.number)
        return super(Renew, cls).renew_contracts(contracts)
