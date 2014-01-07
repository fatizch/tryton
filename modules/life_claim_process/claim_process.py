import copy

from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Loss',
    ]


class Loss:
    __name__ = 'claim.loss'

    @classmethod
    def __setup__(cls):
        super(Loss, cls).__setup__()
        cls.benefits = copy.copy(cls.benefits)
        cls.benefits.on_change_with += ['covered_person']
