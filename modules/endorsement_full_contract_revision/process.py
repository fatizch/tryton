from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Process',
    ]


class Process:
    __name__ = 'process'

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls.kind.selection.append(
            ('full_contract_revision', 'Full Contract Revision'))
