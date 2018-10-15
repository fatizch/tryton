# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
import datetime

from sql import Table, Column

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.migrator import migrator, tools


__all__ = [
    'MigratorBank',
    'MigratorBankAccount',
    'MigratorBankAgency'
    ]


class MigratorBank(migrator.Migrator):
    """Migrator Bank"""

    __name__ = 'migrator.bank'

    @classmethod
    def __setup__(cls):
        super(MigratorBank, cls).__setup__()
        cls.table = Table('bank')
        cls.func_key = 'bic'
        cls.model = 'bank'
        cls.columns = {k: k for k in ('bic', 'party')}
        cls.error_messages.update({
                'existing_bic': "bank already exists with bic '%s'",
                })

    @classmethod
    def init_cache(cls, rows, **kwargs):
        super(MigratorBank, cls).init_cache(rows)
        cls.cache_obj['party'] = tools.cache_from_query('party_party',
            ('code', ), ('code', [r['party'] for r in rows]))
        cls.cache_obj['bank'] = tools.cache_from_query('bank', ('bic', ),
            ('bic', [r['bic'] for r in rows if r['bic']]))

    @classmethod
    def populate(cls, row):
        row = super(MigratorBank, cls).populate(row)
        if 'bic' in row and row['bic'] in cls.cache_obj['bank']:
            cls.raise_error(row, 'existing_bic', (row['bic'],))
        cls.resolve_key(row, 'party', 'party')
        return row

    @classmethod
    def sanitize(cls, row):
        row = super(MigratorBank, cls).sanitize(row)
        if row.get('bic', None) and len(row['bic']) == 8:
            row['bic'] += 'XXX'
        return row

    @classmethod
    def select_remove_ids(cls, ids, excluded, extra_args=None):
        """Return ids without those of objects already present in coog."""
        table_name = cls.model.replace('.', '_')
        existing_ids = tools.cache_from_query(table_name,
            (cls.func_key,)).keys()
        # bis is 11 chars wide but 3 last are optional
        existing_ids += [bic[:8] for bic in existing_ids]
        return list(set(ids) - set(excluded) - set(existing_ids))


class MigratorBankAgency(migrator.Migrator):
    """Migrator Bank agency"""

    __name__ = 'migrator.bank_agency'

    @classmethod
    def __setup__(cls):
        super(MigratorBankAgency, cls).__setup__()
        cls.table = Table('bank_agency')
        cls.columns = {k: k for k in ('id', 'bic', 'name', 'bank_code',
                'branch_code')}
        cls.error_messages.update({
                'existing_agency': ("bank agency already exists with code '%s'"
                " and branch '%s'"),
                })

    @classmethod
    def init_cache(cls, rows, **kwargs):
        cls.cache_obj['bank'] = tools.cache_from_query('bank', ('bic',),
            ('bic', [r['bic'] for r in rows]))
        cls.cache_obj['agency'] = tools.cache_from_query(
            'bank_agency', ('bank_code', 'branch_code'),
            ('bank_code', [r['bank_code'] for r in rows]))

    @classmethod
    def sanitize(cls, row):
        row = super(MigratorBankAgency, cls).sanitize(row)
        if row.get('bic', None) and len(row['bic']) == 8:
            row['bic'] += 'XXX'
        return row

    @classmethod
    def populate(cls, row):
        row = super(MigratorBankAgency, cls).populate(row)
        key = (row['bank_code'], row['branch_code'])
        if key in cls.cache_obj['agency']:
            cls.raise_error(row, 'existing_agency', key)
        cls.resolve_key(row, 'bic', 'bank', 'bank')
        return row

    @classmethod
    def migrate_rows(cls, rows, ids, **kwargs):
        BankAgency = Pool().get('bank.agency')
        to_create = []
        for agency, _rows in groupby(rows, lambda row: row['bic']):
            agency_rows = list(_rows)
            for row in agency_rows:
                try:
                    row = cls.populate(row)
                except migrator.MigrateError as e:
                    cls.logger.error(e)
                    if e.code == 'existing_agency':
                        continue
                    else:
                        break
                to_create.append(BankAgency(**row)._save_values)
        if to_create:
            ids = BankAgency.create(to_create)
            return dict(zip(ids, to_create))


class MigratorBankAccount(migrator.Migrator):
    """Migrator bank account"""

    __name__ = 'migrator.bank_account'

    @classmethod
    def __setup__(cls):
        super(MigratorBankAccount, cls).__setup__()
        cls.table = Table('bank_accounts')
        cls.model = 'bank.account'
        cls.func_key = 'iban'
        cls.columns = {
            'party': 'party',
            'start_date': 'start_date',
            'end_date': 'end_date',
            'iban': 'iban',
            'bic': 'bic',
            'identification': 'identification',
            }

    @classmethod
    def init_update_cache(cls, rows):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        cls.cache_obj['update'] = {}
        numbers = [row[cls.func_key] for row in rows]
        if not numbers:
            return
        Account = pool.get(cls.model)
        account = Account.__table__()
        number = pool.get('bank.account.number').__table__()
        accounts = account.join(number, condition=(
                Column(number, 'account') == Column(account, 'id')))
        query = accounts.select(account.id, account.start_date,
            where=(
                Column(number, 'number_compact').in_(numbers)
            ))
        cursor.execute(*query)
        update = {}
        accounts = Account.browse([row[0] for row in cursor.fetchall()])
        for account in accounts:
            update[account.number.replace(' ', '')] = account
        cls.cache_obj['update'] = update

    @classmethod
    def init_cache(cls, rows, **kwargs):
        super(MigratorBankAccount, cls).init_cache(rows, **kwargs)
        cls.cache_obj['bank'] = tools.cache_from_query('bank', ('bic', ),
            ('bic', [r['bic'] for r in rows if r['bic']]))
        ibans = [r['iban'] for r in rows if r['iban']]
        parties = [r['party'] for r in rows]
        cls.cache_obj['party'] = tools.cache_from_search('party.party',
                'code', ('code', 'in', parties))
        if ibans:
            cls.cache_obj['account'] = tools.cache_from_search('bank.account',
                'number', ('number', 'in', ibans))
        umrs = [r['identification'] for r in rows if r.get('identification')]
        if umrs:
            cls.cache_obj['sepa_mandate'] = tools.cache_from_query(
                'account_payment_sepa_mandate',
                ('identification', ), ('identification', umrs))

    @classmethod
    def sanitize(cls, row):
        row = super(MigratorBankAccount, cls).sanitize(row)
        if len(row['bic']) == 8:
            row['bic'] += 'XXX'
        row['start_date'] = datetime.datetime.strptime(
            row['start_date'], '%Y-%m-%d').date()
        row['end_date'] = datetime.datetime.strptime(
            row['end_date'], '%Y-%m-%d').date()
        return row

    @classmethod
    def populate(cls, row):
        row['active'] = True
        row['owners'] = []
        party_code = row.get('party')
        if party_code in cls.cache_obj['party']:
            row['owners'] = [
                ('add', [cls.cache_obj['party'][party_code].id])]
        if row['bic']:
            row['bank'] = cls.cache_obj['bank'][row['bic']]
        if row['iban'] not in cls.cache_obj.get('update', {}):
            row['numbers'] = [
                ('create', [{'number': row['iban'], 'type': 'iban'}])]
        return row

    @classmethod
    def update_records(cls, rows):
        pool = Pool()
        Model = pool.get(cls.model)
        if rows:
            to_update = {}
            for row in rows:
                obj = cls.cache_obj['update'][row[cls.func_key]]
                func_key = row[cls.func_key]
                row = {k: row[k] for k in row
                    if k in set(Model._fields) - {'id', }}
                to_update[func_key] = [[obj], row]
            Model.write(*sum(to_update.values(), []))
            return rows
        return []

    # @classmethod
    # def migrate_rows(cls, rows, ids, **kwargs):
    #     super(MigratorBankAccount, cls).migrate_rows(
    #         rows, ids, **kwargs)
    #     cls.migrate_sepa_mandate(rows)

    @classmethod
    def migrate_sepa_mandate(cls, rows):
        pool = Pool()
        # Create sepa mandates
        SepaMandate = pool.get('account.payment.sepa.mandate')
        sepa_to_create = {}
        # Group rows by iban to handle bank accounts with multiple owners
        for iban, _rows in groupby(rows, lambda row: row['iban']):
            if not iban:
                continue
            iban_rows = list(_rows)
            for iban_row in iban_rows:
                if iban_row['identification'] in cls.cache_obj['sepa_mandate']:
                    cls.logger.info("Skip SEPA '%s' already present" %
                        iban_row['identification'])
                    continue
                if not iban_row['identification']:
                    cls.logger.info('SEPA No sepa mandate information for '
                        'bank_account.id=%s' % iban_row['id'])
                    continue
                try:
                    cls.resolve_key(iban_row, 'iban', 'account',
                        dest_key='account')
                except migrator.MigrateError as e:
                    cls.logger.error(e)
                    continue
                if iban_row['account']:
                    sepa_to_create[iban_row['identification']] = {
                        'account_number': iban_row['account'].numbers[0].id,
                        'signature_date': iban_row['signature_date'],
                        'identification': iban_row['identification'],
                        'party': iban_row['party_obj'],
                        'state': 'validated',
                        }
        if sepa_to_create:
            SepaMandate.create(sepa_to_create.values())
            cls.cache_obj['sepa_mandate'].update(sepa_to_create)

    @classmethod
    def select_remove_ids(cls, ids, excluded, **kwargs):
        existing_ids = tools.cache_from_search('bank.account', 'number',
            ('number', 'in', ids))
        return list(set(ids) - set(excluded) - set(existing_ids))

    @classmethod
    def migrate(cls, ids, **kwargs):
        res = super(MigratorBankAccount, cls).migrate(ids, **kwargs)
        if not res:
            return []
        ids = [res[r]['iban'] for r in res]
        clause = Column(cls.table, cls.func_key).in_(ids)
        cls.delete_rows(tools.CONNECT_SRC, cls.table, clause)
