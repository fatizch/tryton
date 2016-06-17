from trytond.pool import PoolMeta


__metaclass__ = PoolMeta

__all__ = [
    'ExtraData',
    ]


class ExtraData:
    __name__ = 'extra_data'

    @classmethod
    def __setup__(cls):
        super(ExtraData, cls).__setup__()
        cls.kind.selection.append(('loan', 'Loan'))
