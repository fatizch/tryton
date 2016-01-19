from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Level',
    ]


class Level:
    __name__ = 'account.dunning.level'

    def get_contract_from_dunning(self):
        return lambda x: x.contract.contract_set.contracts[0] if x.contract \
            and x.contract.contract_set else x.contract
