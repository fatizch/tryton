from trytond.pool import PoolMeta

__all__ = [
    'Contract',
    ]
__metaclass__ = PoolMeta


class Contract:
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls.agent.domain.append(('second_level_commission', '=', False))
