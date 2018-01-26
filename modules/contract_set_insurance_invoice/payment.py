from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Payment',
    ]


class Payment:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment'

    @classmethod
    def _group_per_contract_key(cls, payment):
        res = super(Payment, cls)._group_per_contract_key(payment)
        if not res:
            return None
        contract = res[0]
        if contract.contract_set:
            return tuple(contract.contract_set.contracts)
        return res
