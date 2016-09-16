# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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
        table = TableHandler(cls, module_name)

        # These indexes optimizes invoice generation
        # And certainly other coog services
        table.index_action('company', 'remove')
        table.index_action(['company', 'id'], 'add')
        table.index_action(['invoice', 'company'], 'add')

    @classmethod
    def _account_domain(cls, type_):
        # Allow to use 'other' type for invoice line accounts
        result = super(InvoiceLine, cls)._account_domain(type_)
        if 'other' not in result:
            result.append('other')
        return result


class Invoice(export.ExportImportMixin, Printable):
    __name__ = 'account.invoice'
    _func_key = 'number'

    icon = fields.Function(
        fields.Char('Icon'),
        'on_change_with_icon')
    color = fields.Function(
        fields.Char('Color'),
        'get_color')
    business_kind = fields.Selection([('', '')], 'Business Kind',
        states={'readonly': Eval('state') != 'draft'}, depends=['state'])
    business_kind_string = business_kind.translated('business_kind')

    @classmethod
    def __register__(cls, module_name):
        super(Invoice, cls).__register__(module_name)
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)
        table.index_action(['state', 'company'], 'add')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls.move.select = True
        cls.cancel_move.select = True
        cls.cancel_move.states['invisible'] = ~Eval('cancel_move')
        cls.state_string = cls.state.translated('state')

    @classmethod
    def view_attributes(cls):
        return super(Invoice, cls).view_attributes() + [
            ('/tree', 'colors', Eval('color')),
            ]

    @classmethod
    def check_modify(cls, invoices):
        if not Transaction().context.get('_payment_term_change', False):
            super(Invoice, cls).check_modify(invoices)

    @classmethod
    def update_taxes(cls, invoices, exception=False):
        if not Transaction().context.get('_payment_term_change', False):
            super(Invoice, cls).update_taxes(invoices, exception)

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
        elif self.amount_to_pay_today > 0 or self.total_amount < 0:
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
        elif self.amount_to_pay_today > 0 or self.total_amount < 0:
            return 'red'
        elif self.state == 'posted':
            return 'blue'
        return 'black'

    @classmethod
    def change_term(cls, invoices, new_term, new_invoice_date):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Event = pool.get('event')
        to_post, to_reconcile = [], []
        to_reconcile = []
        with Transaction().set_context(_payment_term_change=True):
            previous_moves = [x.move for x in invoices]
            cls.write(invoices, {
                    'payment_term': new_term.id,
                    'move': None,
                    'invoice_date': new_invoice_date
                    })
            for invoice, move in zip(invoices, previous_moves):
                invoice.create_move()
                to_post.append(invoice.move)
                to_post.append(move.cancel())
                reconciliation = []
                for line in move.lines + to_post[-1].lines:
                    if line.account != invoice.account:
                        continue
                    if line.reconciliation:
                        break
                    reconciliation.append(line)
                else:
                    if reconciliation:
                        to_reconcile.append(reconciliation)
        Move.post(to_post)
        for lines in to_reconcile:
            Line.reconcile(lines)
        Event.notify_events(invoices, 'change_payment_term')

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
