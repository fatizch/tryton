# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.server_context import ServerContext

from trytond.modules.coog_core import export, fields, model
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


class Invoice(model.CoogSQL, export.ExportImportMixin, Printable):
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
    reconciliation_date = fields.Function(
        fields.Date('Reconciliation Date'), 'get_reconciliation_date')
    taxes_included = fields.Function(
        fields.Boolean('Taxes Included'),
        loader='get_taxes_included')

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
        cls._transitions -= {('cancel', 'draft')}
        cls._buttons.update({
                'draft': {
                    'invisible': (If(Eval('state') == 'cancel', True,
                            cls._buttons['draft']['invisible'])),
                    },
                })
        cls._error_messages.update({
                'bad_taxes_included_config': 'A given invoice '
                '(%(invoice_name)s) must have a uniform tax management method '
                'across products.',
                })

    @classmethod
    def view_attributes(cls):
        return super(Invoice, cls).view_attributes() + [
            ('/tree', 'colors', Eval('color')),
            ]

    def get_reconciliation_date(self, name):
        dates = []
        for line in self.lines_to_pay:
            if line.reconciliation:
                dates.append(line.reconciliation.create_date)
        if not dates:
            return None
        return max(dates)

    @classmethod
    def validate(cls, invoices):
        with model.error_manager():
            for invoice in invoices:
                if len({bool(x.product.taxes_included) for x in invoice.lines
                            if x.product and x.taxes}) > 1:
                    cls.append_functional_error('bad_taxes_included_config',
                        {'invoice_name': invoice.rec_name})

    @classmethod
    def check_modify(cls, invoices):
        if not Transaction().context.get('_payment_term_change', False):
            super(Invoice, cls).check_modify(invoices)

    def get_taxes_included(self, name=None):
        # Validate enforces that taxes_included field is synced on lines'
        # product, so we only need to get one.
        for line in getattr(self, 'lines', []):
            if not line.taxes:
                continue
            if not line.product:
                continue
            return line.product.taxes_included
        return False

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

    def _get_taxes(self):
        with ServerContext().set_context(taxes_initial_base=defaultdict(int)):
            return super(Invoice, self)._get_taxes()

    @classmethod
    def _compute_tax_line(cls, amount, base, tax):
        line = super(Invoice, cls)._compute_tax_line(amount, base, tax)
        ServerContext().get('taxes_initial_base')[line] += base
        return line

    def _round_taxes(self, taxes):
        '''
            Tax included option is only available if taxes are rounded per line
            This code implements the Sum Preserving Rounding algorithm
        '''
        if not self.taxes_included or not self.currency:
            return super(Invoice, self)._round_taxes(taxes)
        expected_amount_non_rounded = 0
        sum_of_rounded = 0
        initial_data = ServerContext().get('taxes_initial_base')
        for taxline in taxes.itervalues():
            if expected_amount_non_rounded == 0:
                # Add base amount only for the first tax
                expected_amount_non_rounded = initial_data[taxline]
            expected_amount_non_rounded += taxline['amount']
            for attribute in ('base', 'amount'):
                taxline[attribute] = self.currency.round(taxline[attribute])
            if sum_of_rounded == 0:
                sum_of_rounded = taxline['base']
            sum_of_rounded += taxline['amount']
            rounded_of_sum = self.currency.round(expected_amount_non_rounded)
            if sum_of_rounded != rounded_of_sum:
                taxline['amount'] += rounded_of_sum - sum_of_rounded
                sum_of_rounded += rounded_of_sum - sum_of_rounded
            assert rounded_of_sum == sum_of_rounded
        for k in initial_data:
            initial_data[k] = self.currency.round(initial_data[k])
