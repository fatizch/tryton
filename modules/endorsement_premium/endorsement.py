from trytond.pool import PoolMeta
from trytond import backend
from trytond.transaction import Transaction


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
        cursor = Transaction().cursor
        if TableHandler.table_exist(cursor,
                'contract_premium-account_tax__history'):
            TableHandler.drop_table(cursor, 'contract.premium-account.tax',
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
