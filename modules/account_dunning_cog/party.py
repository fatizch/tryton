from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    ]


class Party:
    __name__ = 'party.party'

    @classmethod
    def _export_skips(cls):
        return super(Party, cls)._export_skips() | {'dunning_procedure'}
