from trytond.pool import PoolMeta


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
