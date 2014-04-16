from trytond.model import fields
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Invoice',
    'InvoiceLine',
    ]


class Invoice:
    __name__ = 'account.invoice'

    start = fields.Function(
        fields.Date('Start Date'),
        'get_contract_invoice', searcher='search_contract_invoice')
    end = fields.Function(
        fields.Date('End Date'),
        'get_contract_invoice', searcher='search_contract_invoice')
    contract = fields.Function(
        fields.Many2One('contract', 'Contract'),
        'get_contract_invoice', searcher='search_contract_invoice')

    @classmethod
    def get_contract_invoice(cls, instances, name):
        res = dict((m.id, None) for m in instances)
        cursor = Transaction().cursor

        contract_invoice = Pool().get('contract.invoice').__table__()
        invoice = cls.__table__()

        query_table = invoice.join(contract_invoice, type_='LEFT',
            condition=(contract_invoice.invoice == invoice.id))

        cursor.execute(*query_table.select(invoice.id,
                getattr(contract_invoice, name)))

        for invoice_id, value in cursor.fetchall():
            res[invoice_id] = value
        return res

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


class InvoiceLine:
    __name__ = 'account.invoice.line'
    # XXX maybe change for the description
    contract_insurance_start = fields.Date('Start Date')
    contract_insurance_end = fields.Date('End Date')

    @property
    def origin_name(self):
        pool = Pool()
        Premium = pool.get('contract.premium')
        name = super(InvoiceLine, self).origin_name
        if isinstance(self.origin, Premium):
            name = self.origin.get_parent().rec_name
        return name

    @classmethod
    def _get_origin(cls):
        return super(InvoiceLine, cls)._get_origin() + [
            'contract.premium']
