# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Table, Column, Null

from trytond.pool import Pool
from trytond.modules.migrator import migrator, tools

__all__ = [
    'MigratorPayment',
    ]


class MigratorPayment(migrator.Migrator):
    """Migrator Payment."""

    __name__ = 'migrator.payment'

    @classmethod
    def __setup__(cls):
        super(MigratorPayment, cls).__setup__()
        cls.table = Table('payment')
        cls.model = 'account.payment'
        cls.cache_obj = {'party': {}, 'sepa_mandate': {}, 'journal': {}}
        cls.columns = {k: k for k in ('id', 'party', 'amount', 'date',
            'description', 'kind', 'state', 'sepa_mandate', 'merged_id',
            'sepa_mandate_sequence_type')}
        cls._default_config_items.update({
                'account': None,
                'journal': None,
                })

    @classmethod
    def select(cls, **kwargs):
        """Select all payments that are not reconciled, as migration of
        reconciliations takes care of creating reconciled payments.
        """
        reconciliation = Table('lettrage')
        return (cls.table.join(reconciliation, 'LEFT OUTER',
                condition=(Column(cls.table, cls.columns['id']) ==
                    Column(reconciliation, cls.columns['id']))).select(
                Column(cls.table, cls.columns['id']),
                where=Column(reconciliation, cls.columns['id']) == Null),
            cls.func_key)

    @classmethod
    def init_cache(cls, rows, **kwargs):
        pool = Pool()
        Account = pool.get('account.account')
        Journal = pool.get('account.journal')
        cls.cache_obj['party'] = tools.cache_from_search('party.party', 'code',
            ('code', 'in', [r['party'] for r in rows]))
        cls.cache_obj['sepa_mandate'] = tools.cache_from_search(
            'account.payment.sepa.mandate', 'identification',
            ('identification', 'in', [r['sepa_mandate'] for r in rows if
                r['sepa_mandate']]))
        cls.cache_obj['group'] = tools.cache_from_search(
            'account.payment.group', 'number')
        cls.cache_obj['account'] = Account.search(
            [('code', '=', cls.get_conf_item('account_code'))])[0]
        cls.cache_obj['journal'] = Journal.search(
            [('code', '=', cls.get_conf_item('journal_code'))])[0]

    @classmethod
    def create_move_line(cls, row):
        pool = Pool()
        Move = pool.get('account.move')
        Period = pool.get('account.period')

        company = pool.get('company.company')(1)
        move = Move(extracted=True,
            journal=cls.cache_obj['journal'],
            description=row['description'],
            date=row['date'],
            company=company,
            post_date=row['date'],
            state='posted',
            origin='account.payment,%s' % row['payment'],
            number=row['description'],
            post_number=row['description'],
            period=Period.find(company.id, date=row['date']))
        MoveLine = Pool().get('account.move.line')
        line = MoveLine(company=move.company,
            description=row['description'],
            party=row['party'],
            payment_date=row['date'],
            account=cls.cache_obj['account'],
            credit=row['amount'],
            state='valid')
        move.lines = [line]
        move.save()
        return move.lines[0]

    @classmethod
    def populate(cls, row):
        row['description'] = row['id']
        cls.resolve_key(row, 'party', 'party', dest_attr='id')
        row['state'] = 'draft'
        if row['kind'] == 'payable':
            row['description'] = 'MIGRATION_PAYABLE_%s' % row['id']
        if row['sepa_mandate']:
            cls.resolve_key(row, 'sepa_mandate', 'sepa_mandate',
                dest_attr='id')
            row['group'] = 'MIGRATION_SEPA'
        else:
            row['group'] = 'MIGRATION_MANUAL'
        cls.resolve_key(row, 'group', 'group', dest_attr='id')
        row['is_migrated'] = True
        return row

    @classmethod
    def migrate_rows(cls, rows, ids, **kwargs):
        pool = Pool()
        Payment = Pool().get('account.payment')

        Model = pool.get(cls.model)
        to_create = {}
        for row in rows:
            try:
                row = cls.populate(row)
            except migrator.MigrateError as e:
                cls.logger.error(e)
                continue
            to_create[row[cls.func_key]] = ({k: row[k]
                for k in row if k in set(Model._fields) - {'id', }}, row)
        if to_create:
            payments = Payment.browse(Model.create(
                [x[0] for x in to_create.values()]))
            for payment, row in zip(
                    payments, [x[1] for x in to_create.values()]):
                if payment.kind == 'payable':
                    payment.state = 'succeeded'
                    row['payment'] = payment.id
                    payment.line = cls.create_move_line(row)
                    payment.line.move.save()
            Payment.save([x for x in payments if x.state == 'succeeded'])
        return to_create
