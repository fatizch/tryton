import copy

from trytond.pool import PoolMeta

__all__ = [
    'LifeLossProcess',
]


class LifeLossProcess():
    'Loss'

    __name__ = 'ins_claim.loss'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(LifeLossProcess, cls).__setup__()
        cls.benefits = copy.copy(cls.benefits)
        cls.benefits.on_change_with += ['covered_person']
