# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Table

from trytond.modules.migrator import migrator
from trytond.modules.migrator import tools

__all__ = [
    'MigratorParty',
    'MigratorPartyRelation',
]


class MigratorParty(migrator.Migrator):
    """Migrator Party."""

    __name__ = 'migrator.party'

    @classmethod
    def __setup__(cls):
        super(MigratorParty, cls).__setup__()
        cls.table = Table('party')
        cls.model = 'party.party'
        cls.func_key = 'code'
        cls.transcoding.update({'gender': {}})
        cls.error_messages.update({
                'no_name': 'missing name on party',
                'no_first_name': 'missing first name on party',
                'existing_code': "a party already exists with code '%s'",
                })
        cls.columns = {k: k for k in ('code', 'name', 'is_person',
                'gender', 'first_name', 'birth_date',
                )}

    @classmethod
    def init_cache(cls, rows):
        super(MigratorParty, cls).init_cache(rows)
        cls.cache_obj['party'] = tools.cache_from_query('party_party',
            ('code', ), ('code', [r['code'] for r in rows]))

    @classmethod
    def sanitize(cls, row, parent=None):
        row = super(MigratorParty, cls).sanitize(row)
        err = None
        # Integrity checks
        if not row['name']:
            err = 'no_name'
        elif row['is_person'] and not row['first_name']:
            err = 'no_first_name'
        if err:
            cls.raise_error(row, cls.error_message(err))
            return
        return row

    @classmethod
    def populate(cls, row):
        row = super(MigratorParty, cls).populate(row)
        if (not cls.extra_args['update'] and row['code'] in
                cls.cache_obj['party']):
            cls.raise_error(row, 'existing_code', (row['code'], ))
        return row


class MigratorPartyRelation(migrator.Migrator):
    """Migrator Party Relation."""

    __name__ = 'migrator.party.relation'

    @classmethod
    def __setup__(cls):
        super(MigratorPartyRelation, cls).__setup__()
        cls.table = Table('party_relation')
        cls.transcoding = {'type': {}}
        cls.model = 'party.relation.all'
        cls.columns = {k: k for k in ('id', 'from_', 'to', 'type')}

    @classmethod
    def init_cache(cls, rows):
        cls.cache_obj['party'] = tools.cache_from_query('party_party',
            ('code', ), ('code', [r['from_'] for r in rows] +
                [r['to'] for r in rows]))
        cls.cache_obj['relation_type'] = tools.cache_from_query(
            'party_relation_type', ('code', ))

    @classmethod
    def populate(cls, row):
        cls.resolve_key(row, 'from_', 'party')
        cls.resolve_key(row, 'to', 'party')
        cls.resolve_key(row, 'type', 'relation_type')
        return row
