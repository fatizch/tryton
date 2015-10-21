from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Sequence',
    ]


class Sequence:
    __name__ = 'ir.sequence'

    @classmethod
    def _export_light(cls):
        return super(Sequence, cls)._export_light() | {'company'}
