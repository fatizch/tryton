from trytond.pool import PoolMeta

__all__ = [
    'Process',
    ]


class Process:
    __name__ = 'process'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls.kind.selection.append(('endorsement', 'Contract Endorsement'))
