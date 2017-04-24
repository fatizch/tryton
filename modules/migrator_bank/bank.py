# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
from sql.aggregate import Min
from sql.operators import Not
from sql import Table

from trytond.pool import Pool

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
    def init_cache(cls, rows):
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
    def init_cache(cls, rows):
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
    def migrate_rows(cls, rows, ids):
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
        cls.table = Table('bank_account')
        cls.error_messages.update({
                'no_account_owner': 'No owner for account %s',
                'no_mandate_account': 'No account for mandate %s: %s'
                })
        cls.columns = {k: k for k in ('id', 'party', 'start_date', 'end_date',
                'iban', 'bic', 'identification', 'signature_date')}
        cls.cache_obj = {'bank': {}, 'account': {}, 'sepa_mandate': {},
            'party': {}}

    @classmethod
    def select(cls, extra_args=None):
        """If --create flag then select first row for each iban.
           If no --create flag then select all rows but first for each iban.
        """
        subselect = cls.table.select(Min(cls.table.id),
            group_by=cls.table.iban)
        if 'create' in extra_args and extra_args['create']:
            select = cls.table.select(cls.table.id, cls.table.iban,
                where=cls.table.id.in_(subselect))
        else:
            select = cls.table.select(cls.table.id, cls.table.iban,
                where=Not(cls.table.id.in_(subselect)))
        select.order_by = (cls.table.iban)
        return select, cls.func_key

    @classmethod
    def select_extract_ids(cls, select_key, rows):
        codes = []
        for iban, _rows in groupby(rows, lambda x: x['iban']):
            codes.append([x['id'] for x in _rows])
        return codes

    @classmethod
    def init_cache(cls, rows):
        cls.cache_obj['bank'] = tools.cache_from_query('bank', ('bic', ),
            ('bic', [r['bic'] for r in rows if r['bic']]))
        ibans = [r['iban'] for r in rows if r['iban']]
        if ibans:
            cls.cache_obj['account'] = tools.cache_from_search('bank.account',
                'number', ('number', 'in', ibans))
        umrs = [r['identification'] for r in rows if r['identification']]
        if umrs:
            cls.cache_obj['sepa_mandate'] = tools.cache_from_query(
                'account_payment_sepa_mandate',
                ('identification', ), ('identification', umrs))
        cls.cache_obj['party'] = tools.cache_from_query('party_party',
            ('code', ), ('code', [r['party'] for r in rows]))

    @classmethod
    def sanitize(cls, row):
        row = super(MigratorBankAccount, cls).sanitize(row)
        if len(row['bic']) == 8:
            row['bic'] += 'XXX'
        return row

    @classmethod
    def populate(cls, row):
        try:
            cls.resolve_key(row, 'party', 'party', dest_key='party_obj')
            cls.resolve_key(row, 'bic', 'bank')
        except migrator.MigrateError as e:
            cls.logger.error(e)
            return
        return row

    @classmethod
    def migrate_rows(cls, rows, ids, cursor_src=None):
        pool = Pool()
        BankAccount = pool.get('bank.account')

        to_write = []
        currency = Pool().get('currency.currency')(1)
        rows = filter(None, [cls.populate(r) for r in rows])

        # Group rows by iban to handle bank accounts with multiple owners
        for iban, _rows in groupby(rows, lambda row: row['iban']):
            iban_rows = list(_rows)

            if not iban_rows:
                cls.logger.error(cls.error_message('no_account_owner') % iban)
                continue
            owners = [r['party_obj'] for r in iban_rows]

            if iban in cls.cache_obj['account']:
                cls.logger.info('Update owners for iban %s' % iban)
                to_write.append([BankAccount(
                    cls.cache_obj['account'][iban].id)])
                to_write.append({'owners': [('add', owners)]})
            else:
                acc = (iban, {
                        'owners': [('add', owners)],
                        'numbers': [
                            ('create', [{'number': iban, 'type': 'iban'}]),
                            ],
                        'bank': iban_rows[0]['bic'],
                        'start_date': None,
                        'currency': currency,
                        })
                cls.logger.info('Creating iban %s' % acc[0])
                cls.cache_obj['account'][acc[0]] = BankAccount.create(
                    [acc[1]])[0]
        if to_write:
            BankAccount.write(*to_write)
        cls.migrate_sepa_mandate(rows)

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
