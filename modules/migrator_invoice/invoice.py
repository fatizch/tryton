# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from itertools import chain
from collections import defaultdict

from sql import Table

from trytond.pool import Pool
from trytond.modules.migrator import migrator, tools

__all__ = [
    'MigratorInvoice',
    'MigratorInvoiceLine'
    ]


class MigratorInvoice(migrator.Migrator):
    """Migrator Invoice"""

    __name__ = 'migrator.invoice'

    @classmethod
    def __setup__(cls):
        super(MigratorInvoice, cls).__setup__()
        cls.table = Table('invoice')
        cls.model = 'account.invoice'
        cls.func_key = 'number'
        cls.cache_obj = {'journal': {}, 'contract': {}}
        cls.columns = {k: k for k in ('contract_number', 'number',
                'invoice_date', 'start', 'end', 'state', 'description',
                'account', 'company', 'currency',
                'invoice_address', 'is_commission_invoice', 'journal', 'party',
                'payment_term', 'type', 'business_kind')}
        cls.error_messages.update({
                'no_address': "no address on subscriber '%s'",
                })

    @classmethod
    def init_cache(cls, rows):
        cls.cache_obj['journal'] = Pool().get('account.journal').search(
            [('type', '=', 'revenue')], limit=1)[0]
        cls.cache_obj['contract'] = tools.cache_from_query('contract',
            ('contract_number', ),
            ('contract_number', [r['contract_number'] for r in rows]))

    @classmethod
    def extra_migrator_names(cls):
        migrators = super(MigratorInvoice, cls).extra_migrator_names()
        return migrators + ['migrator.invoice.line']

    @classmethod
    def populate(cls, row):
        Contract = Pool().get('contract')

        cls.resolve_key(row, 'contract_number',
            'contract', dest_key='contract')
        row['contract'] = Contract(row['contract'])
        row['account'] = row['contract'].subscriber.account_receivable
        row['company'] = row['contract'].company
        row['currency'] = row['contract'].get_currency()
        row['is_commission_invoice'] = False
        row['journal'] = cls.cache_obj['journal']
        row['party'] = row['contract'].subscriber
        row['payment_term'] = row['contract'].billing_informations[
            0].payment_term
        row['type'] = 'out'
        row['business_kind'] = 'contract_invoice'
        row['state'] = 'draft'
        if row['contract'].subscriber.addresses:
            row['invoice_address'] = row['contract'].subscriber.addresses[0]
        else:
            cls.raise_error(row, 'no_address', (row['contract'].subscriber, ))
        return row

    @classmethod
    def migrate_rows(cls, rows, ids):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ContractInvoice = pool.get('contract.invoice')

        to_create = defaultdict(list)
        for row in rows:
            try:
                row = cls.populate(row)
            except migrator.MigrateError as e:
                cls.logger.error(e)
                continue
            to_create[row['contract_number']].append(ContractInvoice(
                    contract=row['contract'],
                    invoice=Invoice(**row),
                    start=row['start'],
                    end=row['end'],
                    ))

        if to_create:
            ContractInvoice.create([x._save_values
                for x in chain.from_iterable(to_create.values())])
            for _migrator in cls.extra_migrator_names():
                pool.get(_migrator).migrate([r['number'] for r in rows])
        return to_create


class MigratorInvoiceLine(migrator.Migrator):
    """Migrator Invoice Line"""

    __name__ = 'migrator.invoice.line'

    @classmethod
    def __setup__(cls):
        super(MigratorInvoiceLine, cls).__setup__()
        cls.table = Table('invoice_line')
        cls.model = 'account.invoice.line'
        cls.func_key = 'invoice_number'
        cls.cache_obj = {'invoice': {}, 'loan': {}, 'party': {}}
        cls.columns = {k: k for k in ('id', 'invoice_number', 'coverage_start',
                'coverage_end', 'amount', 'party', 'covered_element', 'loan',
                'taxed_amount')}

    @classmethod
    def init_cache(cls, rows):
        Invoice = Pool().get('account.invoice')

        super(MigratorInvoiceLine, cls).init_cache(rows)
        cls.cache_obj['invoice'] = tools.cache_from_query('account_invoice',
            ('number', ), ('number', [r['invoice_number'] for r in rows]))
        cls.cache_obj['loan'] = tools.cache_from_query('loan', ('number', ),
            ('number', [r['loan'] for r in rows]))
        cls.cache_obj['party'] = tools.cache_from_query('party_party',
            ('code', ), ('code', [r['party'] for r in rows]))
        cls.cache_obj['contract'] = tools.cache_from_query('contract',
            ('contract_number', ), ('contract_number',
                [x.contract.contract_number
                    for x in Invoice.browse(cls.cache_obj['invoice'].values())
                    ]))
        cls.cache_obj['premium'] = tools.cache_from_query('contract_premium',
            ('contract', ), ('contract', cls.cache_obj['contract'].values()))

    @classmethod
    def populate(cls, row):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Contract = pool.get('contract')

        cls.resolve_key(row, 'invoice_number', 'invoice', dest_key='invoice')
        cls.resolve_key(row, 'loan', 'loan')  # used for invoice line detail
        cls.resolve_key(row, 'party', 'party')
        row['invoice'] = Invoice(row['invoice'])
        row['account'] = cls.cache_obj['account']
        row['company'] = row['invoice'].company
        row['description'] = row['invoice'].contract. \
            covered_elements[0].options[0].coverage.name
        row['currency'] = row['invoice'].currency
        row['quantity'] = 1
        row['unit'] = None
        row['unit_price'] = row['amount']
        row['origin'] = str(Contract(cls.cache_obj['contract'][
                    row['invoice'].contract.contract_number]))
        row['invoice_type'] = 'out'
        row['type'] = 'line'
        return row

    @classmethod
    def migrate_rows(cls, rows, ids):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        InvoiceLineDetail = Pool().get('account.invoice.line.detail')
        Premium = pool.get('contract.premium')

        ids = []
        to_create = []
        for row in rows:
            try:
                row = cls.populate(cls.sanitize(row))
            except migrator.MigrateError as e:
                cls.logger.error(e)
                continue
            to_create.append(row)

        if to_create:
            vals = [{k: _row[k] for k in _row
                if k in set(InvoiceLine._fields) - {'id', 'loan'}}
                for _row in to_create]
            ids = InvoiceLine.create(vals)

            # Save detail for each line
            details = []
            for i, invoice_line in enumerate(ids):
                premiums = Premium.search(
                    [('contract', '=', invoice_line.origin),
                        ['OR',
                            [('end', '>=', invoice_line.coverage_start),
                                ('end', '<=', invoice_line.coverage_end)],
                            [('start', '>=', invoice_line.coverage_start),
                                ('start', '<=', invoice_line.coverage_end)],
                            [('start', '<=', invoice_line.coverage_start),
                                ('end', '>=', invoice_line.coverage_end)]]])
                for premium in premiums:
                    detail = InvoiceLineDetail.new_detail_from_premium(premium)
                    detail.invoice_line = invoice_line
                    details.append(detail)
            InvoiceLineDetail.save(details)
        return dict(zip(ids, vals))
