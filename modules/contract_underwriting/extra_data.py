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
        cls.kind.selection.append(('contract_underwriting',
                'Contract Underwriting'))
        cls.kind.selection.append(('option_underwriting',
                'Option Underwriting'))
