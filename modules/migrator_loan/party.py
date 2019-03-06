# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Table

from trytond.pool import Pool

from trytond.modules.migrator import migrator

__all__ = [
    'MigratorLender',
]


class MigratorLender(migrator.Migrator):
    """Migrator Lender"""

    __name__ = 'migrator.lender'

    @classmethod
    def __setup__(cls):
        super(MigratorLender, cls).__setup__()
        cls.table = Table('lenders')
        cls.func_key = 'party'
        cls.model = 'lender'
        cls.columns = {'party': 'party'}

    @classmethod
    def init_cache(cls, rows, **kwargs):
        super(MigratorLender, cls).init_cache(rows, **kwargs)
        parties = Pool().get('party.party').search([
                ('code', 'in', [x['party'] for x in rows])])
        cls.cache_obj['party'] = {p.code: p.id for p in parties}

    @classmethod
    def populate(cls, row):
        party = cls.cache_obj['party'][row['party']]
        return {'party': party}
