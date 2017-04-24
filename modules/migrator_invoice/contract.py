# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

__all__ = [
    'MigratorContract',
    ]


class MigratorContract:
    __metaclass__ = PoolMeta
    __name__ = 'migrator.contract'

    @classmethod
    def extra_migrator_names(cls):
        migrators = super(MigratorContract, cls).extra_migrator_names()
        return migrators + ['migrator.invoice']
