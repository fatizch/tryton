
from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import model, fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'InvoiceLogging',
    'Invoice']


class Invoice:
    __name__ = 'account.invoice'

    @classmethod
    def post(cls, invoices):
        super(Invoice, cls).post(invoices)
        InvoiceLogging = Pool().get('account.invoice.logging')
        InvoiceLogging.create(cls.generate_invoice_logging_list(invoices))

    @classmethod
    def paid(cls, invoices):
        super(Invoice, cls).paid(invoices)
        InvoiceLogging = Pool().get('account.invoice.logging')
        InvoiceLogging.create(cls.generate_invoice_logging_list(invoices))

    @classmethod
    def cancel(cls, invoices):
        super(Invoice, cls).cancel(invoices)
        InvoiceLogging = Pool().get('account.invoice.logging')
        InvoiceLogging.create(cls.generate_invoice_logging_list(invoices))

    @classmethod
    def generate_invoice_logging_list(cls, invoices):
        return [{
                'state': invoice.state,
                'invoice': invoice.id,
                'state_date': utils.today(),
                } for invoice in invoices]


class InvoiceLogging(model.CoopSQL):
    'Invoice Logging'
    __name__ = 'account.invoice.logging'

    state = fields.Selection([
            ('draft', 'Draft'),
            ('validated', 'Validated'),
            ('posted', 'Posted'),
            ('paid', 'Paid'),
            ('cancel', 'Canceled'),
            ], 'State', required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice', required=True,
        ondelete='CASCADE', select=True)
    state_date = fields.Date('State Date')
