# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

__all__ = [
    'MigratorParty',
    ]


class MigratorParty(metaclass=PoolMeta):
    __name__ = 'migrator.party'

    @classmethod
    def __setup__(cls):
        super(MigratorParty, cls).__setup__()
        cls.columns.update({'ssn': 'ssn', 'ssn_key': 'ssn_key'})

    @classmethod
    def populate(cls, row):
        row = super(MigratorParty, cls).populate(row)
        if row['ssn'] and row['ssn_key']:
            row['ssn'] += row['ssn_key']
        return row
