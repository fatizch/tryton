# coding: utf-8

from sql import Table, Column
from itertools import groupby

from trytond.pool import Pool
from trytond.modules.migrator import migrator, tools
from trytond.modules.coog_core import utils


__all__ = [
    'MigratorInvoiceMoveLine',
    'MigratorMoveReconciliation',
    ]


class MigratorInvoiceMoveLine(migrator.Migrator):
    """Migrator Invoice Move Line"""

    __name__ = 'migrator.invoice.move.line'

    @classmethod
    def __setup__(cls):
        super(MigratorInvoiceMoveLine, cls).__setup__()
        cls.table = Table('move_line')
        cls.model = 'account.move.line'
        cls.cache_obj = {'journal': {}, 'contract': {}}
        cls.columns = {k: k for k in ('id', 'date', 'kind',
            'amount', 'contract', 'description', 'maturity_date',
            'payment_date', 'state', 'invoice_number')}
        cls.error_messages.update({
                'no_billing_info': 'no billing info on contract %s',
                })

    @classmethod
    def init_cache(cls, rows):
        Invoice = Pool().get('account.invoice')

        cls.cache_obj['invoice'] = {k: Invoice(v) for (k, v) in
            tools.cache_from_query('account_invoice', ('number', ),
                ('number', [r['invoice_number'] for r in rows])).iteritems()}
        cls.cache_obj['contract'] = tools.cache_from_query('contract',
            ('contract_number', ),
            ('contract_number', [x.contract.contract_number
                    for x in cls.cache_obj['invoice'].values()]))

    @classmethod
    def query_data(cls, ids):
        select = super(MigratorInvoiceMoveLine, cls).query_data(ids)
        select.order_by = (Column(cls.table, cls.columns['invoice_number']))
        return select

    @classmethod
    def migrate_rows(cls, rows_all, ids, **kwargs):
        pool = Pool()
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        for invoice_number, _rows in groupby(rows_all,
                key=lambda r: r['invoice_number']):
            rows = list(_rows)

            invoice = cls.cache_obj['invoice'][invoice_number]
            billing_info = utils.get_good_version_at_date(
                invoice.contract, 'billing_informations', invoice.start)

            if not billing_info:
                cls.logger.error(cls.error_message('no_billing_info') % (
                    None, invoice.contract.contract_number))
                continue
            direct_debit = billing_info.direct_debit
            if direct_debit:
                invoice.sepa_mandate = billing_info.sepa_mandate.id

            move_lines = invoice._get_move_line_invoice_line()
            move_lines += invoice._get_move_line_invoice_tax()

            for row in rows:
                row = cls.populate(cls.sanitize(row))
                try:
                    payment_line = invoice._get_move_line(row['maturity_date'],
                        -row['amount'])
                except AttributeError:
                    cls.logger.error(cls.error_message('no_billing_info') % (
                        row[cls.func_key], invoice.contract.contract_number))
                    continue
                payment_line['description'] = row['id']
                if not direct_debit:
                    payment_line['payment_date'] = None
                elif row['maturity_date'] < utils.today():
                    payment_line['payment_date'] = row['maturity_date']
                    payment_line['maturity_date'] = row['maturity_date']
                move_lines.append(payment_line)

            accounting_date = invoice.accounting_date or invoice.invoice_date
            period_id = Period.find(invoice.company.id, date=accounting_date)
            invoice_move = Move(
                journal=invoice.journal.id,
                state='posted',
                period=period_id,
                date=accounting_date,
                post_date=accounting_date,
                company=invoice.company.id,
                lines=move_lines,
                origin=invoice,
                extracted=True,
                number='MIGR_%s' % invoice_number)
            invoice_move.save()
            invoice.move = invoice_move
            invoice.state = 'posted'
            invoice.save()

        return {x: None for x in ids}


class MigratorMoveReconciliation(migrator.Migrator):
    """Migrator Move Reconciliation"""

    __name__ = 'migrator.move.reconciliation'

    @classmethod
    def __setup__(cls):
        super(MigratorMoveReconciliation, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 10,
                })
        cls.table = Table('move_reconciliation')
        cls.model = 'account.move.reconciliation'
        cls.func_key = 'name'
        cls.columns = {k: k for k in ('name', 'payment', 'amount',
            'move_line')}
        cls.error_messages.update({
                'no_payment': 'no payment',
                'no_line_to_pay': 'no move line to pay',
                'invalid_line_to_pay': 'invalid line to pay (%s)',
                })

    @classmethod
    def select(cls, extra_args):
        select = cls.table.select(*[Column(cls.table, cls.columns['name']).as_(
                'name'), Column(cls.table, cls.columns['identifiant_paiement']
                ).as_('payment')],
            order_by=(Column(cls.table, cls.columns['identifiant_paiement'])))
        return select, cls.func_key

    @classmethod
    def select_extract_ids(cls, select_key, rows):
        return [(x['name'], x['payment']) for x in rows]

    @classmethod
    def select_remove_ids(cls, ids, excluded, extra_args=None):
        """Return ids without those of objects already present in coog.
        """
        table_name = cls.model.replace('.', '_')
        existing_ids = tools.cache_from_query(table_name, (cls.func_key,))
        set_ids = set([x[0] for x in ids])
        set_existing_ids = set(existing_ids)
        res = set_ids - set_existing_ids
        return [x for x in ids if x[0] in res]

    @classmethod
    def select_group_ids(cls, ids):
        """Group together ids that must be handled by same job
        """
        res = []
        for payment, _ids in groupby(ids, lambda name_pay: name_pay[1]):
            res.append([x[0] for x in _ids])
        return res

    @classmethod
    def query_data(cls, ids):
        payment = Table('paiement')
        columns = cls.select_columns()
        columns.extend([
                payment.tiers.as_('party'),
                payment.type.as_('kind'),
                payment.etat.as_('state'),
                payment.date.as_('date'),
                payment.mandat_sepa.as_('sepa_mandate'),
                payment.id_regroupement_sepa.as_('merged_id'),
                payment.type_sequence_mandat.as_('sepa_mandate_sequence_type'),
                ])
        select = cls.table.join(payment,
            condition=((cls.table.identifiant_paiement ==
                payment.identifiant_paiement))
            ).select(*columns,
                where=(cls.table.identifiant_lettrage.in_(ids)))
        return select

    @classmethod
    def init_cache(cls, rows):
        pool = Pool()
        Period = pool.get('account.period')
        cls.cache_obj['payment'] = {}
        cls.cache_obj['move_line'] = tools.cache_from_query(
            'account_move_line', ('description',),
            ('description', [r['move_line'] for r in rows]))
        if 'period' not in cls.cache_obj:
            periods = Period.search([])
            cls.cache_obj['period'] = {}
            for p in periods:
                cls.cache_obj['period'][p.start_date.year] = p.id

    @classmethod
    def populate(cls, row):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Payment = Pool().get('account.payment')
        cls.resolve_key(row, 'payment', 'payment')
        cls.resolve_key(row, 'move_line', 'move_line')
        row['move_line'] = MoveLine(row['move_line'])
        row['payment'] = Payment(row['payment'])
        return row

    @classmethod
    def create_reconciled_payments(cls, rows):
        def load_payments_cache(rows):
            cls.cache_obj['payment'].update(tools.cache_from_query(
                'account_payment',
                ('description',),
                ('description', [r['payment'] for r in rows])))

        MigratorPayment = Pool().get('migrator.payment')
        load_payments_cache(rows)
        rows = [r for r in rows
            if r['payment'] not in cls.cache_obj['payment']]
        if rows:
            MigratorPayment.init_cache(rows)
            MigratorPayment.migrate_rows(rows, [x['payment'] for x in rows])
            load_payments_cache(rows)

    @classmethod
    def migrate_rows(cls, rows_all, ids, **kwargs):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Move = pool.get('account.move')
        Payment = Pool().get('account.payment')
        Reconciliation = pool.get('account.move.reconciliation')
        reconciliations = []
        payments = []
        for payment, _rows in groupby(rows_all, key=lambda r: r['payment']):
            rows = list(_rows)
            for row in rows:
                row['payment'] = row['payment'] + '_' + row['name']
                row['id'] = row['payment']
                # Note: row['amount'] corresponds to the lettering amount!

            cls.create_reconciled_payments(rows)
            for row in rows:
                try:
                    row = cls.populate(row)
                except migrator.MigrateError as e:
                    cls.logger.error(e)
                    continue
                line_to_pay = row['move_line']
                if line_to_pay.state != 'valid':
                    cls.logger.error(cls.error_message(
                            'invalid_line_to_pay') % (row['name'],
                            line_to_pay.id))
                    continue
                invoice = line_to_pay.origin
                period = cls.cache_obj['period'][row['payment'].date.year]

                move = Move(description='Migration payment',
                    state='posted',
                    period=period,
                    move_company=invoice.company.id,
                    date=row['payment'].date,
                    post_date=row['payment'].date,
                    number='MIGR_PAY_%s' % invoice.number,
                    journal=row['payment'].journal.clearing_journal.id,
                    origin='account.payment,%s' % row['payment'].id,
                    extracted=True)

                payment_line = MoveLine(account=line_to_pay.account.id,
                    description=move.description,
                    party=line_to_pay.party.id,
                    credit=line_to_pay.debit,
                    debit=line_to_pay.credit,
                    contract=invoice.contract.id,
                    maturity_date=row['payment'].date)

                compensation_line = MoveLine(
                    account=row['payment'].journal.clearing_account.id,
                    description=move.description,
                    credit=line_to_pay.credit,
                    debit=line_to_pay.debit)

                move.lines = [payment_line, compensation_line]
                move.save()

                reconciliation = Reconciliation(name=row['name'],
                    lines=[line_to_pay.id] + [move.lines[-1].id],
                    date=row['payment'].date)
                reconciliations.append(reconciliation)
                row['payment'].party = row['move_line'].party
                row['payment'].line = row['move_line'].id
                row['payment'].state = 'succeeded'
                payments.append(row['payment'])
        try:
            Payment.save(payments)
        except Exception as e:
            cls.logger.error('Payment save failed: %s.' % (str(e)))
        Reconciliation.save(reconciliations)
        return {r.id: None for r in reconciliations}
