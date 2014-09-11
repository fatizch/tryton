from sql import Cast
from sql.aggregate import Sum
from sql.operators import Concat

from trytond.model import fields
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

from trytond.modules.cog_utils import coop_string, utils

__metaclass__ = PoolMeta
__all__ = [
    'Invoice',
    'InvoiceLine',
    ]


class Invoice:
    __name__ = 'account.invoice'

    start = fields.Function(
        fields.Date('Start Date'),
        'get_contract_invoice_field', searcher='search_contract_invoice')
    end = fields.Function(
        fields.Date('End Date'),
        'get_contract_invoice_field', searcher='search_contract_invoice')
    base_amount = fields.Function(
        fields.Numeric('Base amount'),
        'get_base_amount')
    contract = fields.Function(
        fields.Many2One('contract', 'Contract'),
        'get_contract_invoice_field', searcher='search_contract_invoice')
    contract_invoice = fields.Function(
        fields.Many2One('contract.invoice', 'Contract Invoice'),
        'get_contract_invoice_field')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'),
        'get_currency_symbol')
    fees = fields.Function(
        fields.Numeric('Fees'),
        'get_fees')

    def get_base_amount(self, name):
        return self.untaxed_amount - self.fees

    @classmethod
    def get_contract_invoice_field(cls, instances, name):
        res = {}
        cursor = Transaction().cursor

        contract_invoice = Pool().get('contract.invoice').__table__()
        invoice = cls.__table__()

        query_table = invoice.join(contract_invoice, 'LEFT OUTER',
            condition=(contract_invoice.invoice == invoice.id))

        if name == 'contract_invoice':
            name = 'id'

        cursor.execute(*query_table.select(invoice.id,
                getattr(contract_invoice, name),
                where=(invoice.id.in_([x.id for x in instances]))))

        for invoice_id, value in cursor.fetchall():
            res[invoice_id] = value
        return res

    def get_currency_symbol(self, name):
        return self.currency.symbol if self.currency else ''

    @classmethod
    def get_fees(cls, invoices, name):
        pool = Pool()
        cursor = Transaction().cursor
        premium = pool.get('contract.premium').__table__()
        invoice_line = pool.get('account.invoice.line').__table__()

        query_table = invoice_line.join(premium, condition=(
                invoice_line.invoice.in_([x.id for x in invoices]))
            & (Concat('contract.premium,', Cast(premium.id, 'VARCHAR'))
                == invoice_line.origin)
            & (premium.rated_entity.like('account.fee.description,%')))

        cursor.execute(*query_table.select(invoice_line.invoice,
                Sum(invoice_line.unit_price), group_by=[invoice_line.invoice]))

        result = dict((x.id, 0) for x in invoices)
        for invoice_id, total in cursor.fetchall():
            result[invoice_id] = total
        return result

    @classmethod
    def search_contract_invoice(cls, name, clause):
        cursor = Transaction().cursor

        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]

        contract_invoice = Pool().get('contract.invoice').__table__()
        invoice = cls.__table__()

        query_table = invoice.join(contract_invoice, type_='LEFT',
            condition=(contract_invoice.invoice == invoice.id))

        cursor.execute(*query_table.select(invoice.id,
                where=Operator(getattr(contract_invoice, name),
                    getattr(cls, name).sql_format(value))))

        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    def _order_contract_invoice_field(name):
        def order_field(tables):
            ContractInvoice = Pool().get('contract.invoice')
            field = ContractInvoice._fields[name]
            table, _ = tables[None]
            contract_invoice_tables = tables.get('contract_invoice')
            if contract_invoice_tables is None:
                contract_invoice = ContractInvoice.__table__()
                contract_invoice_tables = {
                    None: (contract_invoice,
                        contract_invoice.invoice == table.id),
                    }
                tables['contract_invoice'] = contract_invoice_tables
            return field.convert_order(name, contract_invoice_tables,
                ContractInvoice)
        return staticmethod(order_field)
    order_start = _order_contract_invoice_field('start')
    order_end = _order_contract_invoice_field('end')

    def get_synthesis_rec_name(self, name):
        if self.contract:
            if self.start and self.end:
                return '%s - %s - (%s - %s) [%s]' % (
                    self.contract.rec_name,
                    self.currency.amount_as_string(self.total_amount),
                    coop_string.date_as_string(self.start),
                    coop_string.date_as_string(self.end),
                    coop_string.translate_value(self, 'state'))
            else:
                return '%s - %s [%s]' % (self.contract.rec_name,
                    self.currency.amount_as_string(self.total_amount),
                    coop_string.translate_value(self, 'state'))
        else:
            if self.start and self.end:
                return '- %s - (%s - %s) [%s]' % (
                    self.currency.amount_as_string(self.total_amount),
                    coop_string.date_as_string(self.start),
                    coop_string.date_as_string(self.end),
                    coop_string.translate_value(self, 'state'))
            else:
                return '%s - %s [%s]' % (
                    self.currency.amount_as_string(self.total_amount),
                    coop_string.translate_value(self, 'state'))

    def get_icon(self, name=None):
        if self.reconciled:
            return 'coopengo-reconciliation'

    def udpate_move_line_from_billing_information(self, line,
            billing_information):
        return {'payment_date':
            billing_information.get_direct_debit_planned_date(line)}

    def _get_move_line(self, date, amount):
        line = super(Invoice, self)._get_move_line(date, amount)
        if not self.contract or not self.contract_invoice or not line:
            return line
        contract_revision_date = max(line['maturity_date'],
            utils.today())
        with Transaction().set_context(contract_revision_date=
                contract_revision_date):
            res = self.udpate_move_line_from_billing_information(
                line, self.contract.billing_information)
            line.update(res)
            return line

    def update_invoice_before_post(self):
        self.invoice_date = self.contract_invoice.start
        return {'invoice_date': self.contract_invoice.start}

    @classmethod
    def post(cls, invoices):
        updated_invoices = []
        for invoice in invoices:
            if (invoice.state not in ('validated', 'draft') or
                    not invoice.contract_invoice):
                continue
            updated_invoices += [[invoice],
                invoice.update_invoice_before_post()]
        if updated_invoices:
            cls.write(*updated_invoices)
        super(Invoice, cls).post(invoices)

    def check_cancel_move(self):
        # account_invoice.check_cancel_move makes it impossible to cancel moves
        # of out_invoices.
        if not self.contract:
            super(Invoice, self).check_cancel_move()

    def print_invoice(self):
        # Don't print invoice report if it's a contract invoice
        if not self.contract:
            super(Invoice, self).print_invoice()


class InvoiceLine:
    __name__ = 'account.invoice.line'
    # XXX maybe change for the description
    coverage_start = fields.Date('Start Date')
    coverage_end = fields.Date('End Date')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'),
        'get_currency_symbol')

    @property
    def origin_name(self):
        pool = Pool()
        Premium = pool.get('contract.premium')
        name = super(InvoiceLine, self).origin_name
        if isinstance(self.origin, Premium):
            name = self.origin.parent.rec_name
        return name

    @classmethod
    def _get_origin(cls):
        return super(InvoiceLine, cls)._get_origin() + [
            'contract.premium']

    def get_currency_symbol(self, name):
        return self.currency.symbol if self.currency else ''
