from trytond.pool import PoolMeta

__all__ = [
    'MigratorInvoice',
    ]


class MigratorInvoice:
    __metaclass__ = PoolMeta
    __name__ = 'migrator.invoice'

    @classmethod
    def extra_migrator_names(cls):
        migrators = super(MigratorInvoice, cls).extra_migrator_names()
        return migrators + ['migrator.invoice.move.line']
