from trytond.pool import PoolMeta

from trytond.modules.migrator import tools

__all__ = [
    'MigratorParty',
    ]


class MigratorParty(metaclass=PoolMeta):
    __name__ = 'migrator.party'

    @classmethod
    def __setup__(cls):
        super(MigratorParty, cls).__setup__()
        cls.columns.update({'birth_zip': 'birth_zip',
                'birth_city': 'birth_city',
                'birth_country': 'birth_country'})

    @classmethod
    def init_cache(cls, rows, **kwargs):
        super(MigratorParty, cls).init_cache(rows, **kwargs)
        cls.cache_obj['birth_country'] = tools.cache_from_search(
            'country.country',
            'code', ('code', 'in', set([r['birth_country'] for r in rows])))

    @classmethod
    def populate(cls, row):
        row = super(MigratorParty, cls).populate(row)
        row['birth_country'] = cls.cache_obj['birth_country'].get(
            row['birth_country'], None)
        return row
