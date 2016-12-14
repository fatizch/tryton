# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import re

from itertools import groupby
from sql import Column, Table

from trytond.pool import Pool

from trytond.modules.migrator import migrator
from trytond.modules.migrator import tools
from trytond.modules.party_cog.contact_mechanism import VALID_EMAIL_REGEX


__all__ = [
    'MigratorCountry',
    'MigratorAddress',
    'MigratorContact',
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
    def init_cache(cls, rows):
        super(MigratorZip, cls).init_cache(rows)
        cls.cache_obj['country'] = tools.cache_from_query('country_country',
            ('code',))
        cls.cache_obj['zip'] = tools.cache_from_query('country_zip',
            ('zip', 'country', 'city', 'line5'))

    @classmethod
    def sanitize(cls, row):
        row = super(MigratorZip, cls).sanitize(row)
        if not row.get('country_code', None):
            row['country_code'] = cls.get_conf_item('default_country_code')
        return row

    @classmethod
    def populate(cls, row):
        row = super(MigratorZip, cls).populate(row)
        cls.resolve_key(row, 'country_code', 'country', dest_key='country')
        return row

    @classmethod
    def migrate_rows(cls, rows, ids):
        to_upsert = {}
        done_keys = set()
        for (country, _zip, city, line5), _rows in groupby(rows, lambda r: (
                        r['country_code'], r['zip'], r['city'], r['line5'])):
            row = cls.populate(list(_rows)[0])
            key = (row['zip'], row['country'], rowfds['city'], row['line5'])
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
            cls.upsert_records(to_upsert.values())
        return to_upsert


class MigratorAddress(migrator.Migrator):
    """Migrator address"""

    __name__ = 'migrator.address'

    @classmethod
    def __setup__(cls):
        super(MigratorAddress, cls).__setup__()
        cls.table = 'address'
        cls.model = 'party.address'
        cls.columns = {k: k for k in ('id', 'party', 'start_date',
            'end_date', 'name', 'line3', 'street', 'streetbis', 'zip', 'city',
            'country_code', 'country', 'sequence')}
        cls._default_config_items.update({
                'default_country_code': 'FR',
                })
        cls.error_messages.update({
            'duplicate_address': "Address already imported",
            })

    @classmethod
    def query_data(cls, numbers):
        select = super(MigratorAddress, cls).query_data(numbers)
        select.order_by = (Column(cls.table, cls.columns['start_date']))
        return select

    @classmethod
    def init_cache(cls, rows):
        super(MigratorAddress, cls).init_cache(rows)
        cls.cache_obj['country'] = tools.cache_from_query('country_country',
            ('code', ))
        cls.cache_obj['party'] = tools.cache_from_query('party_party',
            ('code', ), ('code', [r['party'] for r in rows]))

    @classmethod
    def populate(cls, row):
        Party = Pool().get('party.party')
        row = super(MigratorAddress, cls).populate(row)
        cls.resolve_key(row, 'party', 'party')
        cls.resolve_key(row, 'country_code', 'country', dest_key='country')
        for adr in Party(row['party']).addresses:
            if all(row[x] == getattr(adr, x, None) for x in ('name', 'street',
                    'line3', 'zip', 'streetbis', 'start_date', 'city')):
                cls.raise_error(row, 'duplicate_address')
        return row


class MigratorContact(migrator.Migrator):
    """Migrator contact"""

    __name__ = 'migrator.contact'

    @classmethod
    def __setup__(cls):
        super(MigratorContact, cls).__setup__()
        cls.table = 'contact_mechanism'
        cls.model = 'party.contact_mechanism'
        cls.columns = {k: k for k in ('id', 'party', 'email',
            'phone', 'mobile', 'fax')}
        cls.error_messages.update({
            'no_contact': "no contact mechanism set in input data",
            'skip_has_contact': "skip contact as party already has contacts",
            'skip_email': 'skip email %s for party %s',
            })

    @classmethod
    def init_cache(cls, rows):
        super(MigratorContact, cls).init_cache(rows)
        cls.cache_obj['party'] = tools.cache_from_query('party_party',
            ('code', ), ('code', [r['party'] for r in rows]))

    @classmethod
    def populate(cls, row):
        Party = Pool().get('party.party')
        contacts = []
        cls.resolve_key(row, 'party', 'party')
        if len(Party(row['party']).contact_mechanisms):
            cls.logger.warning(cls.error_message('skip_has_contact') %
                row['id'])
            return contacts
        if not any([row[k] for k in ('email', 'phone', 'mobile', 'fax')]):
            cls.logger.warning(cls.error_message('no_contact') % row['id'])
            return contacts
        for kind in ('email', 'phone', 'mobile', 'fax'):
            if row[kind]:
                if (kind == 'email') and not re.match(VALID_EMAIL_REGEX,
                        row[kind]):
                    cls.logger.warning(cls.error_message('skip_email') % (
                        row[cls.func_key], row[kind], row['party']))
                    continue
                contacts.append({'type': kind,
                    'value': row[kind],
                    'party': row['party']})
        return contacts

    @classmethod
    def migrate_rows(cls, rows, ids):
        pool = Pool()
        to_create = []
        for row in rows:
            try:
                to_create.extend(cls.populate(row))
            except migrator.MigrateError as e:
                cls.logger.error(e)
                continue
        ids = []
        if to_create:
            Mechanisms = pool.get('party.contact_mechanism')
            ids = Mechanisms.create(to_create)
        return dict(zip(ids, to_create))
