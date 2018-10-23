# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from itertools import groupby
from datetime import datetime

from sql import Table, Column, Literal

from trytond.modules.migrator import migrator
from trytond.modules.migrator import tools
from trytond.pool import Pool
from trytond.transaction import Transaction

__all__ = [
    'MigratorParty',
    'MigratorContactMechanism',
    'MigratorCompany',
    'MigratorPartyRelation',
    'MigratorInterlocutor',
    ]


class MigratorParty(migrator.Migrator):
    """Migrator Party."""

    __name__ = 'migrator.party'

    @classmethod
    def __setup__(cls):
        super(MigratorParty, cls).__setup__()
        cls.table = Table('parties')
        cls.model = 'party.party'
        cls.func_key = 'code'
        cls.transcoding.update({'gender': {}})
        cls.error_messages.update({
                'no_name': 'missing name on party',
                'no_first_name': 'missing first name on party',
                'existing_code': "a party already exists with code '%s'",
                })
        cls.columns = {k: k for k in ('code', 'name', 'first_name',
                'birth_name', 'ssn', 'ssn_key', 'gender', 'birth_date',
                'extra_data'
                )}

    @classmethod
    def init_update_cache(cls, rows):
        ids = [row[cls.func_key] for row in rows]
        cls.cache_obj['update'] = tools.cache_from_search('party.party',
            'code', ('code', 'in', (ids)))

    @classmethod
    def init_cache(cls, rows, **kwargs):
        super(MigratorParty, cls).init_cache(rows, **kwargs)
        cls.cache_obj['party'] = tools.cache_from_query('party_party',
            ('code', ), ('code', [r['code'] for r in rows]))

    @classmethod
    def sanitize(cls, row, parent=None):
        row = super(MigratorParty, cls).sanitize(row)
        err = None
        # Integrity checks
        row['birth_date'] = datetime.strptime(
            row['birth_date'], '%Y-%m-%d').date()
        if not row['name']:
            err = 'no_name'
        if err:
            cls.raise_error(row, cls.error_message(err))
            return
        return row

    @classmethod
    def populate(cls, row):
        row = super(MigratorParty, cls).populate(row)
        row['all_addresses'] = []
        row['is_person'] = True
        row['extra_data'] = eval(row['extra_data'] or '{}')
        row['ssn'] += row['ssn_key']
        return row

    @classmethod
    def migrate(cls, ids, **kwargs):
        res = super(MigratorParty, cls).migrate(ids, **kwargs)
        if not res:
            return []
        ids = [res[r]['code'] for r in res]
        clause = Column(cls.table, cls.func_key).in_(ids)
        cls.delete_rows(tools.CONNECT_SRC, cls.table, clause)


class MigratorContactMechanism(migrator.Migrator):
    'Migrate Contact Mechanism'

    __name__ = 'migrator.contact'

    @classmethod
    def __setup__(cls):
        super(MigratorContactMechanism, cls).__setup__()
        cls.table = Table('contact_mechanisms')
        cls.model = 'party.contact_mechanism'
        cls.func_key = 'uid'
        cls.columns = {
            'party': 'party',
            'email': 'email',
            'phone': 'phone',
            'mobile': 'mobile',
            'fax': 'fax',
            'sequence': 'sequence',
            }

    @classmethod
    def init_update_cache(cls, rows):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        cls.cache_obj['update'] = {}

        parties = [row['party'] for row in rows]
        sequences = [int(row['sequence']) for row in rows]
        types = [row['type'] for row in rows]

        if not parties or not sequences or not types:
            return

        Contact = pool.get(cls.model)
        contact_table = Contact.__table__()
        party_table = pool.get('party.party').__table__()
        query_table = contact_table.join(party_table,
            condition=(
                Column(contact_table, 'party') == Column(party_table, 'id')))
        cursor.execute(*query_table.select(
            contact_table.id, party_table.code,
            contact_table.sequence, contact_table.type,
            where=(
                Column(party_table, 'code').in_(parties) &
                Column(contact_table, 'sequence').in_(sequences) &
                Column(contact_table, 'type').in_(types)
                )))
        contacts = Contact.browse([row[0] for row in cursor.fetchall()])
        update = {}
        for contact in contacts:
            uid = ':'.join([
                contact.party.code,
                str(contact.sequence),
                contact.type
                ])
            update[uid] = contact
        cls.cache_obj['update'] = update

    @classmethod
    def init_cache(cls, rows, **kwargs):
        super(MigratorContactMechanism, cls).init_cache(rows, **kwargs)
        parties = [r['party'] for r in rows]
        cls.cache_obj['party'] = tools.cache_from_search(
            'party.party', 'code', ('code', 'in', parties))
        cls.cache_obj['create'] = {}

    @classmethod
    def select(cls, **kwargs):
        select_keys = [
            Column(cls.table, 'party'),
            Column(cls.table, 'sequence'),
            Column(cls.table, 'phone'),
            Column(cls.table, 'email'),
            Column(cls.table, 'mobile'),
            Column(cls.table, 'fax'),
            ]
        select = cls.table.select(*select_keys)
        return select, cls.func_key

    @classmethod
    def run_query(cls, select, cursor):
        """
        Run query and then duplicate row for each contact mechanism type.
        """
        rows = super(MigratorContactMechanism, cls).run_query(select, cursor)
        new_rows = []
        mechanisms = ['phone', 'fax', 'email', 'mobile']
        for row in rows:
            row_mech = {k: row.pop(k) for k in mechanisms}
            for k, v in row_mech.items():
                if v:
                    new_row = dict(**row)
                    new_row['value'] = v
                    new_row['type'] = k
                    new_row[cls.func_key] = ':'.join([
                        new_row['party'],
                        new_row['sequence'], new_row['type']])
                    new_rows.append(new_row)
        return new_rows

    @classmethod
    def query_data(cls, ids):
        select = cls.table.select(*cls.select_columns())
        return select

    @classmethod
    def select_extract_ids(cls, select_key, rows):
        ids = []
        for row in rows:
            for type_contact in ['phone', 'email', 'fax', 'mobile']:
                if not row[type_contact]:
                    continue
                ids.append('{}_{}_{}'.format(
                    row.get('party'),
                    row.get('sequence'),
                    type_contact,
                    ))
        return set(ids)

    @classmethod
    def select_remove_ids(cls, ids, excluded, **kwargs):
        table_name = cls.model.replace('.', '_')
        existing_ids = tools.cache_from_query(table_name,
            ('party', 'sequence', 'type')).keys()
        existing = []
        for id_ in existing_ids:
            existing.append('%s_%s_%s' % (id_[0], id_[1], id_[2]))
        return set(ids) - set(existing) - set(excluded)

    @classmethod
    def populate(cls, row):
        party_code = row.get('party')
        if (party_code in cls.cache_obj['party']):
            row['party'] = cls.cache_obj['party'][party_code]
        cls.cache_obj['create'][row[cls.func_key]] = row
        return row

    @classmethod
    def update_records(cls, rows):
        """
        We can't update party so we remove it from rows.
        """
        return super(MigratorContactMechanism, cls).update_records(
            [row for row in rows if row.pop('party') or True])

    @classmethod
    def _group_by_party_sequence(cls, row):
        return row[0], row[1]

    @classmethod
    def migrate(cls, ids, **kwargs):
        res = super(MigratorContactMechanism, cls).migrate(ids, **kwargs)
        if not res:
            return []
        ids = [(res[r]['party'].code if 'party' in res[r] else
                res[r]['uid'].split(':')[0], res[r]['sequence'],
                res[r]['type'], res[r]['value']) for r in res]
        clause = Literal(False)
        ids = sorted(ids, key=cls._group_by_party_sequence)
        for keys, values in groupby(ids,
                key=cls._group_by_party_sequence):
            values = list(values)
            sub_clause = Literal(True)
            for party, seq, type_, value in values:
                sub_clause &= (
                    (cls.table.party == party) &
                    (cls.table.sequence == seq) &
                    (Column(cls.table, type_) == value)
                    )
            clause |= sub_clause
        cls.delete_rows(tools.CONNECT_SRC, cls.table, clause)


class MigratorCompany(migrator.Migrator):
    'Migrate Company'

    __name__ = 'migrator.company'

    @classmethod
    def __setup__(cls):
        super(MigratorCompany, cls).__setup__()
        cls.table = Table('companies')
        cls.model = 'party.party'
        cls.func_key = 'code'
        cls.columns = {
            'code': 'code',
            'name': 'name',
            'commercial_name': 'commercial_name',
            'siren': 'siren',
            'parent_company': 'parent_company',
            'extra_data': 'extra_data',
            }

    @classmethod
    def init_update_cache(cls, rows):
        ids = [row[cls.func_key] for row in rows]
        cls.cache_obj['update'] = tools.cache_from_search('party.party',
            'code', ('code', 'in', (ids)))

    @classmethod
    def populate(cls, row, parent=None):
        Party = Pool().get('party.party')
        row['all_addresses'] = []
        row['is_person'] = False
        row['extra_data'] = eval(row['extra_data'])
        if row['parent_company']:
            # Could not use cache because the parent_record will not be
            # inserted yet
            row['parent_company'] = Party.search([
                    ('code', '=', row['parent_company'])
                    ])[0].id
        return row

    @classmethod
    def migrate(cls, ids, **kwargs):
        res = super(MigratorCompany, cls).migrate(ids, **kwargs)
        if not res:
            return []
        ids = [res[r]['code'] for r in res]
        clause = Column(cls.table, cls.func_key).in_(ids)
        cls.delete_rows(tools.CONNECT_SRC, cls.table, clause)


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
    def init_cache(cls, rows, **kwargs):
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


class MigratorInterlocutor(migrator.Migrator):
    'Migrate Interlocutors'

    __name__ = 'migrator.interlocutor'

    @classmethod
    def __setup__(cls):
        super(MigratorInterlocutor, cls).__setup__()
        cls.table = Table('interlocutors')
        cls.model = 'party.interlocutor'
        cls.func_key = 'uid'
        cls.columns = {
            'company': 'company',
            'interlocutor': 'interlocutor',
            'job': 'job',
            'phone': 'phone',
            'email': 'email',
            'address_sequence': 'address_sequence',
            'start_date': 'start_date',
            'end_date': 'end_date',
            }

    @classmethod
    def init_update_cache(cls, rows):
        pool = Pool()
        Address = pool.get('party.address')
        Interlocutor = pool.get('party.interlocutor')
        cursor = Transaction().connection.cursor()
        cls.cache_obj['update'] = {}
        interlocutor = Interlocutor.__table__()
        party = pool.get('party.party').__table__()
        address = Address.__table__()
        parties = [cls.cache_obj['company'][r['company']].id for r in rows]

        query_table = interlocutor.join(party, condition=(
                interlocutor.party == party.id)).join(address, condition=(
                interlocutor.address == address.id))  # NOQA
        sub_where_clause = Literal(False)
        for r in rows:
            party = cls.cache_obj['company'][r['company']]
            sub_where_clause |= (address.party == party.id)
        sub_query = address.select(address.id, where=sub_where_clause)
        where_clause = (interlocutor.address.in_(sub_query) &
            interlocutor.party.in_(parties))

        query = query_table.select(interlocutor.id, where=where_clause)
        cursor.execute(*query)
        update = {}
        existing_interlocutors = Interlocutor.browse(
            [x[0] for x in cursor.fetchall()])
        update = {}
        for interlocutor in existing_interlocutors:
            uid = '%s:%s' % (interlocutor.name, interlocutor.party.code)
            update[uid] = interlocutor
        cls.cache_obj['update'] = update

    @classmethod
    def init_cache(cls, rows, **kwargs):
        Address = Pool().get('party.address')
        cls.cache_obj['company'] = tools.cache_from_search(
            'party.party', 'code',
            ('code', 'in', [r['company'] for r in rows]))
        addresses = Address.search([
                ('party', 'in', cls.cache_obj['company'].values())
                ])
        cls.cache_obj['address'] = {
            '%s:%s' % (x.party.code, x.sequence): x
            for x in addresses}
        super(MigratorInterlocutor, cls).init_cache(rows, **kwargs)

    @classmethod
    def sanitize(cls, row):
        row = super(MigratorInterlocutor, cls).sanitize(row)
        row['interlocutor'] = row['interlocutor'].strip()
        row['start_date'] = datetime.datetime.strptime(
            row['start_start'], '%Y-%m-%d') if row['start_date'] else None
        row['end_date'] = datetime.datetime.strptime(
            row['end_date'], '%Y-%m-%d') if row['end_date'] else None
        row['address_sequence'] = int(row['address_sequence'])
        return row

    @classmethod
    def create_contact(cls, row):
        party = cls.cache_obj['company'][row['company']]
        mechanisms = ['phone', 'email']
        row_mech = {k: row.pop(k) for k in mechanisms}
        contacts = []
        for k, v in row_mech.items():
            if v:
                new_contact = {
                    'party': party,
                    'value': v,
                    'type': k,
                    'sequence': row['address_sequence'],
                    }
                contacts.append(new_contact)
        return contacts

    @classmethod
    def get_or_create_contacts(cls, code, sequence, row):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        party_table = pool.get('party.party').__table__()
        Contact = pool.get('party.contact_mechanism')
        contact_table = Contact.__table__()

        query_table = contact_table.join(party_table, condition=(
                Column(contact_table, 'party') == Column(party_table, 'id')
                ))
        cursor.execute(*query_table.select(contact_table.id, where=(
                (Column(party_table, 'code') == code) &
                (Column(contact_table, 'sequence') == sequence) &
                (Column(contact_table, 'type').in_(['phone', 'email'])) &
                (Column(contact_table, 'value').in_(
                    [row['phone'], row['email']]))
                )))
        to_add = Contact.browse([r[0] for r in cursor.fetchall()])
        if to_add:
            return [('add', to_add)]
        return [('create', cls.create_contact(row))]

    @classmethod
    def populate(cls, row):
        code = '_'.join([row['company'], str(row['address_sequence'])])
        row['code'] = code
        row['name'] = row['interlocutor']
        row[cls.func_key] = ':'.join(
            [row['interlocutor'], row['company']])
        row['party'] = cls.cache_obj['company'][row['company']]
        address_key = ':'.join([row['company'], str(row['address_sequence'])])
        row['address'] = cls.cache_obj['address'][address_key]
        contacts = cls.get_or_create_contacts(
            row['company'], row['address_sequence'], row)
        row['contact_mechanisms'] = contacts
        return row

    @classmethod
    def select(cls, **kwargs):
        select = cls.table.select(
            *[Column(cls.table, x) for x in cls.columns.keys()])
        return select, cls.func_key

    @classmethod
    def select_extract_ids(cls, select_key, rows):
        ids = []
        cls.init_cache(rows)
        for row in rows:
            ids.append(u'{}_{}'.format(
                row['interlocutor'],
                row['company']))
        return set(ids)

    @classmethod
    def select_remove_ids(cls, ids, excluded, **kwargs):
        pool = Pool()
        interlocutor = pool.get('party.interlocutor').__table__()
        party = pool.get('party.party').__table__()
        address = pool.get('party.address').__table__()
        cursor = Transaction().connection.cursor()

        query_table = interlocutor.join(party, condition=(
                interlocutor.party == party.id)).join(address, condition=(
                address.party == party.id))  # NOQA
        cursor.execute(*query_table.select(interlocutor.name,
                party.code,
                ))
        existing_ids = {
            '%s_%s' % (row[0], row[1]) for
            row in cursor.fetchall()}
        return list(set(ids) - set(excluded) - set(existing_ids))

    @classmethod
    def query_data(cls, ids):
        where_clause = Literal(False)
        for id_ in ids:
            name, company = id_.split('_')
            where_clause |= (
                (cls.table.interlocutor == name) &
                (cls.table.company == company))
        select = cls.table.select(*cls.select_columns(),
            where=where_clause)
        return select

    @classmethod
    def migrate(cls, ids, **kwargs):
        res = super(MigratorInterlocutor, cls).migrate(ids, **kwargs)
        if not res:
            return []
        ids = [(res[r]['party'].code, res[r]['name']) for r in res]
        clause = Literal(False)
        for company, interlocutor in ids:
            clause |= ((Column(cls.table, 'company') == company) &
                (Column(cls.table, 'interlocutor') == interlocutor))
        cls.delete_rows(tools.CONNECT_SRC, cls.table, clause)
        return res
