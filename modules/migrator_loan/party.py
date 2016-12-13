# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Table

from trytond.modules.migrator import migrator
from trytond.modules.migrator import tools

__all__ = [
    'MigratorLender',
]


class MigratorLender(migrator.Migrator):
    """Migrator Lender"""

    __name__ = 'migrator.lender'

    @classmethod
    def __setup__(cls):
        super(MigratorLender, cls).__setup__()
        cls.table = Table('lender')
        cls.func_key = 'code'
        cls.model = 'lender'
        cls.columns = {k: k for k in ('code', 'party')}

    @classmethod
    def init_cache(cls, rows):
        super(MigratorLender, cls).init_cache(rows)
        cls.cache_obj['party'] = tools.cache_from_query('party_party',
            ('code',), ('code', [r['party'] for r in rows]))

    @classmethod
    def populate(cls, row):
        row = super(MigratorLender, cls).populate(row)
        cls.resolve_key(row, 'party', 'party')
        return row
