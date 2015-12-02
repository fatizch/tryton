from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.cog_utils import export, fields
from trytond.modules.report_engine import Printable

__metaclass__ = PoolMeta
__all__ = [
    'Invoice',
    'InvoiceLine',
    ]


class InvoiceLine:
    __name__ = 'account.invoice.line'

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        cls.company.select = False

    @classmethod
    def __register__(cls, module_name):
        super(InvoiceLine, cls).__register__(module_name)
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor()
        table = TableHandler(cursor, cls, module_name)

        # These indexes optimizes invoice generation
        # And certainly other coog services
        table.index_action('company', 'remove')
        table.index_action(['company', 'id'], 'add')
        table.index_action(['invoice', 'company'], 'add')


class Invoice(export.ExportImportMixin, Printable):
    __name__ = 'account.invoice'
    _func_key = 'number'

    icon = fields.Function(
        fields.Char('Icon'),
        'on_change_with_icon')
    color = fields.Function(
        fields.Char('Color'),
        'get_color')

    @classmethod
    def __register__(cls, module_name):
        super(Invoice, cls).__register__(module_name)
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor()
        table = TableHandler(cursor, cls, module_name)
        table.index_action(['state', 'company'], 'add')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls.move.select = True
        cls.cancel_move.select = True
        cls.cancel_move.states['invisible'] = ~Eval('cancel_move')

    @classmethod
    def view_attributes(cls):
        return super(Invoice, cls).view_attributes() + [
            ('/tree', 'colors', Eval('color')),
            ]

    @classmethod
    def is_master_object(cls):
        return True

    @fields.depends('state', 'amount_to_pay_today')
    def on_change_with_icon(self, name=None):
        if self.state == 'cancel':
            return 'invoice_cancel'
        elif self.state == 'paid':
            return 'invoice_paid'
        elif self.state == 'draft':
            return 'invoice_draft'
        elif self.amount_to_pay_today > 0:
            return 'invoice_unpaid'
        elif self.state == 'posted':
            return 'invoice_post'
        else:
            return 'invoice'

    def get_lang(self):
        return self.party.lang.code

    def get_contact(self):
        return self.party

    def get_sender(self):
        return self.company.party

    def get_color(self, name):
        if self.state == 'paid':
            return 'green'
        elif self.state == 'cancel':
            return 'grey'
        elif self.amount_to_pay_today > 0:
            return 'red'
        elif self.state == 'posted':
            return 'blue'
        return 'black'

    @classmethod
    def post(cls, invoices):
        pool = Pool()
        Event = pool.get('event')
        super(Invoice, cls).post(invoices)
        Event.notify_events(invoices, 'post_invoice')

    @classmethod
    def cancel(cls, invoices):
        pool = Pool()
        Event = pool.get('event')
        super(Invoice, cls).cancel(invoices)
        if not Transaction().context.get('deleting_invoice', None):
            Event.notify_events(invoices, 'cancel_invoice')

    @classmethod
    def paid(cls, invoices):
        pool = Pool()
        Event = pool.get('event')
        super(Invoice, cls).paid(invoices)
        Event.notify_events(invoices, 'pay_invoice')

    @classmethod
    def delete(cls, invoices):
        # use deleting_invoice context to allow different behavior in cancel
        # invoice method (as delete call cancel)
        with Transaction().set_context(deleting_invoice=True):
            super(Invoice, cls).delete(invoices)
