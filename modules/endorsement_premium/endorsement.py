from trytond.pool import PoolMeta


__all__ = [
    'ContractFee',
    'EndorsementContract',
    ]


class ContractFee:
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.fee'


class EndorsementContract:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract'

    @classmethod
    def _prepare_restore_history(cls, instances, at_date):
        super(EndorsementContract, cls)._prepare_restore_history(instances,
            at_date)
        for contract in instances['contract']:
            instances['contract.fee'] += contract.fees
