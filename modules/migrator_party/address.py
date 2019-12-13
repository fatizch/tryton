# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
from sql import Column, Table

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.migrator import migrator
from trytond.modules.migrator import tools


__all__ = [
    'MigratorCountry',
    'MigratorAddress',
    'MigratorZip',
]


class MigratorCountry(migrator.Migrator):
    """Migrator country"""

    __name__ = 'migrator.country'

    @classmethod
    def __setup__(cls):
        super(MigratorCountry, cls).__setup__()
        cls.model = 'country.country'
        cls.table = Table('country')
        cls.func_key = 'code'
        cls.columns = {k: k for k in ('code', 'name')}

    @classmethod
    def sanitize(cls, row):
        row = super(MigratorCountry, cls).sanitize(row)
        row['name'] = row['name'].title()
        return row


class MigratorZip(migrator.Migrator):
    """Migrator zip"""

    __name__ = 'migrator.zip'

    @classmethod
    def __setup__(cls):
        super(MigratorZip, cls).__setup__()
        cls.model = 'country.zip'
        cls.table = Table('zip')
        cls.cache_obj = {'zip': {}}
        cls.columns = {k: k for k in ('id', 'zip', 'city', 'country_code',
            'country_name', 'line5')}
        cls._default_config_items.update({'default_country_code': 'FR', })

    @classmethod
    def query_data(cls, ids):
        select = super(MigratorZip, cls).query_data(ids)
        select.order_by = (
            Column(cls.table, cls.columns['country_code']),
            Column(cls.table, cls.columns['zip']),
            Column(cls.table, cls.columns['city']),
            Column(cls.table, cls.columns['line5']),
            )
        select.group_by = select.order_by
        return select

    @classmethod
    def init_cache(cls, rows, **kwargs):
        super(MigratorZip, cls).init_cache(rows, **kwargs)
        cls.cache_obj['country'] = tools.cache_from_query('country_country',
            ('code',))
        cls.cache_obj['zip'] = tools.cache_from_query('country_zip',
            ('zip', 'country', 'city', 'line5'))

    @classmethod
    def sanitize(cls, row):
        row = super(MigratorZip, cls).sanitize(row)
        if not row.get('country_code', None):
            row['country_code'] = cls._default_config_items.get(
                'default_country_code')
        return row

    @classmethod
    def populate(cls, row):
        row = super(MigratorZip, cls).populate(row)
        cls.resolve_key(row, 'country_code', 'country', dest_key='country')
        return row

    @classmethod
    def migrate_rows(cls, rows, ids, **kwargs):
        to_upsert = {}
        done_keys = set()
        for (country, _zip, city, line5), _rows in groupby(rows, lambda r: (
                        r['country_code'], r['zip'], r['city'], r['line5'])):
            row = cls.populate(list(_rows)[0])
            key = (row['zip'], row['country'], row['city'], row['line5'])
            # Call to populate() may return a row with the same values as a
            # previous one, in that case we don't want to add it.
            if key in cls.cache_obj['zip']:
                cls.logger.info('Skip existing zip %s' % row)
                continue
            if key in done_keys:
                cls.logger.info('Skip already processed zip %s' % row)
                continue
            done_keys.add(key)
            to_upsert[key] = row
        if to_upsert:
            cls.upsert_records(list(to_upsert.values()), **kwargs)
        return to_upsert


class MigratorAddress(migrator.Migrator):
    """Migrator address"""

    __name__ = 'migrator.address'

    @classmethod
    def __setup__(cls):
        super(MigratorAddress, cls).__setup__()
        cls.table = Table('addresses')
        cls.model = 'party.address'
        cls.func_key = 'uid'
        cls.columns = {k: k for k in ('party', 'start_date',
            'end_date', 'line1', 'line2', 'line3', 'line4', 'line5', 'zip',
            'city', 'country_code', 'sequence')}
        cls._default_config_items.update({
                'default_country_code': 'FR',
                })
        cls.error_messages.update({
            'duplicate_address': "Address already imported",
            'address_zip_code_required': "The zip code is required for '%s'",
            })

    @classmethod
    def query_data(cls, ids):
        select = cls.table.select(*cls.select_columns())
        where = None
        for func_key in ids:
            sequence = func_key.split('_')[0]
            party = func_key.split('_')[1]
            where_clause = ((cls.table.party == party) |
                    (cls.table.sequence == sequence))
            where = where & where_clause if where else where_clause
        select.order_by = (Column(cls.table, cls.columns['start_date']))
        return select

    @classmethod
    def init_update_cache(cls, rows):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        cls.cache_obj['update'] = {}

        parties = [row['party'] for row in rows]
        sequences = [row['sequence'] for row in rows]
        if not parties or not sequences:
            return

        Address = pool.get(cls.model)
        address_table = Address.__table__()
        party_table = pool.get('party.party').__table__()
        addresses = address_table.join(party_table, condition=(
            address_table.party == party_table.id))
        query = addresses.select(
            address_table.id, party_table.code,
            address_table.sequence, address_table.start_date,
            where=(
                Column(party_table, 'code').in_(parties) &
                Column(address_table, 'sequence').in_(sequences)))
        cursor.execute(*query)
        addresses = Address.browse([row[0] for row in cursor.fetchall()])
        update = {}
        for address in addresses:
            code = address.party.code
            seq = str(address.sequence)
            uid = ':'.join([code, seq])
            update[uid] = address
        cls.cache_obj['update'] = update

    @classmethod
    def init_cache(cls, rows, **kwargs):
        super(MigratorAddress, cls).init_cache(rows, **kwargs)
        parties = [r['party'] for r in rows]
        codes = [r['country_code'] for r in rows]
        cls.cache_obj['party'] = tools.cache_from_search('party.party',
            'code', ('code', 'in', parties))
        cls.cache_obj['country'] = tools.cache_from_search('country.country',
            'code', ('code', 'in', codes))

    @classmethod
    def populate(cls, row):
        row = super(MigratorAddress, cls).populate(row)
        cls.resolve_key(row, 'party', 'party')
        cls.resolve_key(row, 'country_code', 'country', dest_key='country')
        if not row['zip']:
            cls.raise_error(row, 'address_zip_code_required',
                (row['party'].code,))
        for adr in row['party'].addresses:
            if all(row[x] == getattr(adr, x, None) for x in ('street',
                    'zip', 'start_date', 'city')):
                cls.raise_error(row, 'duplicate_address')
        return row

    @classmethod
    def sanitize(cls, row, parent=None):
        row = super(MigratorAddress, cls).sanitize(row)
        street = '\n'.join([row['line2'] or '',
            row['line3'] or '', row['line4'] or '', row['line5'] or ''])
        row.pop('line1')
        row.pop('line2')
        row.pop('line3')
        row.pop('line4')
        row.pop('line5')
        row['street'] = street
        row['sequence'] = str(row['sequence'])
        row['uid'] = ':'.join([row['sequence'], row['party']])
        return row

    @classmethod
    def select(cls, **kwargs):
        select_keys = [
            Column(cls.table, 'sequence'),
            Column(cls.table, 'party'),
            ]
        select = cls.table.select(*select_keys)
        return select, cls.func_key

    @classmethod
    def select_extract_ids(cls, select_key, rows):
        ids = []
        for row in rows:
            ids.append('{}_{}'.format(
                row.get('sequence'),
                row.get('party'),
                ))
        return set(ids)

    @classmethod
    def select_remove_ids(cls, ids, excluded, **kwargs):
        table_name = cls.model.replace('.', '_')
        existing_ids = list(tools.cache_from_query(table_name,
            ('sequence', 'party')).keys())
        existing_ids = {'%s_%s' % (x[0], x[1]) for x in existing_ids}
        return list(set(ids) - set(excluded) - set(existing_ids))

    @classmethod
    def migrate(cls, ids, **kwargs):
        res = super(MigratorAddress, cls).migrate(ids, **kwargs)
        if not res:
            return []
        if kwargs.get('delete', False):
            ids = []
            Party = Pool().get('party.party')
            for r in res:
                party_code = Party(res[r]['party']).code
                ids.append(
                    (party_code, res[r]['sequence']),
                    )
            clause = Column(cls.table, 'party').in_([x[0] for x in ids]
                ) & Column(cls.table, 'sequence').in_([x[1] for x in ids])
            cls.delete_rows(tools.CONNECT_SRC, cls.table, clause)
