# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond import backend


__all__ = [
    'ContractFee',
    'Premium',
    'EndorsementContract',
    ]


class ContractFee:
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.fee'


class Premium:
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'contract.premium'

    @classmethod
    def __register__(cls, module_name):
        super(Premium, cls).__register__(module_name)

        # Migrate from 1.6 : Remove premium-tax relation
        TableHandler = backend.get('TableHandler')
        if TableHandler.table_exist(
                'contract_premium-account_tax__history'):
            TableHandler.drop_table('contract.premium-account.tax',
                'contract_premium-account_tax__history', cascade=True)


class EndorsementContract:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract'

    @classmethod
    def _get_restore_history_order(cls):
        order = super(EndorsementContract, cls)._get_restore_history_order()
        contract_idx = order.index('contract')
        order.insert(contract_idx + 1, 'contract.fee')
        order.append('contract.premium')
        return order

    @classmethod
    def _prepare_restore_history(cls, instances, at_date):
        super(EndorsementContract, cls)._prepare_restore_history(instances,
            at_date)
        instances['contract.premium'] = []
        for contract in instances['contract']:
            instances['contract.premium'] += contract.premiums
            for fee in contract.fees:
                instances['contract.fee'].append(fee)
                instances['contract.premium'] += fee.premiums
            for option in contract.options:
                instances['contract.premium'] += option.premiums
