# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from sql import Cast
from sql.aggregate import Max
from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If
from trytond.tools import grouped_slice
from trytond.transaction import Transaction
from trytond.server_context import ServerContext

from trytond.modules.coog_core import export, fields, model, utils, coog_sql
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
    form_color = fields.Function(
        fields.Char('Color'),
        'get_color')
    business_kind = fields.Selection([('', '')], 'Business Kind',
        states={'readonly': Eval('state') != 'draft'}, depends=['state'])
    business_kind_string = business_kind.translated('business_kind')
    reconciliation_date = fields.Function(
        fields.Date('Reconciliation Date',
            states={'invisible': ~Eval('reconciliation_date')}),
        'get_reconciliation_date')
    taxes_included = fields.Function(
        fields.Boolean('Taxes Included'),
        loader='get_taxes_included')

    @classmethod
    def __register__(cls, module_name):
        super(Invoice, cls).__register__(module_name)
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)
        table.index_action(['state', 'company'], 'add')
        utils.add_reference_index(cls, module_name)

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
    def set_number(cls, invoices):
        '''
        This method is almost a copy past from the original one (trytond
        account_invoice module).
        We need to override it completely in order to postpone the strict
        sequence get number which is putting down the performances in case of
        concurrency uses.
        See _delayed_set_number docstring for more informations.
        '''
        if ServerContext().get('from_batch', False):
            return super(Invoice, cls).set_number(invoices)
        filtered_invoices = []
        Date = Pool().get('ir.date')
        filtered_invoices = []
        for invoice in invoices:
            if invoice.state in {'posted', 'paid'}:
                continue
            if not invoice.tax_identifier:
                invoice.tax_identifier = invoice.get_tax_identifier()
            if invoice.number:
                continue
            if not invoice.invoice_date and invoice.type == 'out':
                invoice.invoice_date = Date.today()
            filtered_invoices.append(invoice)
        cls.save(invoices)
        return cls._delayed_set_number(filtered_invoices,
            substitute_hook=cls._negative_id_as_number)

    @classmethod
    def _negative_id_as_number(cls, invoices):
        for invoice in invoices:
            invoice.number = str(invoice.id * -1)
        cls.save(invoices)

    @classmethod
    @model.pre_commit_transaction()
    def _delayed_set_number(cls, invoices, sub_transactions=None):
        '''
        This method will be executed using a two phase commit manager.
        Once the function is called, its execution is delayed at the commit
        time of the DataManager which occurs juste before the main transaction
        commit.
        The code of this function is a copy past from the trytond set_number
        and get_next_number methods (account_invoice_module). We need to bypass
        these in order to postpone the code execution just before the main
        transaction commit and then, significantly improve the concurrency
        set_number performances. (i.e: while multiple users applies
        endorsements which recalculate / rebill at the same time.
        '''
        pool = Pool()
        Period = pool.get('account.period')
        sub_transaction = None
        to_write = []
        if sub_transactions is None:
            sub_transactions = []
        for invoice in invoices:
            pattern = {}
            period_id = Period.find(
                invoice.company.id, date=(invoice.accounting_date or
                    invoice.invoice_date),
                test_state=invoice.type != 'in')
            period = Period(period_id)
            fiscalyear = period.fiscalyear
            pattern.setdefault('company', invoice.company.id)
            pattern.setdefault('fiscalyear', fiscalyear.id)
            pattern.setdefault('period', period.id)
            invoice_type = invoice.type
            # JCA : Avoid forced read of invoice lines unless necessary
            forced_type = ServerContext().get('forced_invoice_type', None)
            if forced_type:
                invoice_type += forced_type
            else:
                if (all(l.amount < 0 for l in invoice.lines if l.product)
                        and invoice.total_amount < 0):
                    invoice_type += '_credit_note'
                else:
                    invoice_type += '_invoice'
            for invoice_sequence in fiscalyear.invoice_sequences:
                if invoice_sequence.match(pattern):
                    sequence = getattr(
                        invoice_sequence, '%s_sequence' % invoice_type)
                    break
            else:
                invoice.raise_user_error('no_invoice_sequence', {
                        'invoice': invoice.rec_name,
                        'fiscalyear': fiscalyear.rec_name,
                        })
            # sub_transaction given as parameter will be popped from
            # arguments by the decorator. This last will use it as main
            # transaction for it's code execution if valid otherwise it
            # will creates a new one.
            # Any raised exception will be returned instead of the function
            # result, so we must handle it properly and not forget to
            # rollback the sub transaction.
            number, sub_transaction = \
                invoice._sub_transaction_get_sequence(sequence,
                    sub_transaction=sub_transaction)
            sub_transactions.append(sub_transaction)
            if isinstance(number, Exception):
                raise number
            to_write += [[invoice], {'number': number}]
        with ServerContext().set_context(pre_commit_number=True):
            if to_write:
                cls.write(*to_write)

    @model.sub_transaction_retry(10, 1000)
    def _sub_transaction_get_sequence(self, sequence):
        '''
        This decorated function will be executed in a sub transaction.
        If the code fails (concurrent access for instance),
        the decorator will reexecute the code within a new sub transaction.
        The decorator takes the number of max retries and the time in ms
        to wait.
        '''
        with Transaction().set_context(date=self.invoice_date):
            Sequence = Pool().get('ir.sequence.strict')
            return Sequence.get_id(sequence.id)

    @classmethod
    def view_attributes(cls):
        return super(Invoice, cls).view_attributes() + [
            ('/tree', 'colors', Eval('color')),
            ('/form/group[@id="invisible"]', 'states', {'invisible': True}),
            (
                '/form/notebook/page/group/group/group/field[@name="state"]',
                'states',
                {'field_color': Eval('form_color')}
                ),
            ]

    @classmethod
    def get_reconciliation_date(cls, invoices, name):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        reconciliation = pool.get('account.move.reconciliation').__table__()
        line = pool.get('account.move.line').__table__()
        move = pool.get('account.move').__table__()
        invoice_table = cls.__table__()

        result = {x.id: None for x in invoices}

        for invoices_slice in grouped_slice(invoices):
            query_table = reconciliation.join(line, condition=(
                    line.reconciliation == reconciliation.id)
                ).join(move, condition=(
                    line.move == move.id)
                ).join(invoice_table, condition=(
                    move.origin == coog_sql.TextCat(cls.__name__ + ',',
                        Cast(invoice_table.id, 'VARCHAR'))))

            cursor.execute(*query_table.select(invoice_table.id,
                Max(reconciliation.create_date),
                where=((invoice_table.id.in_([x.id for x in invoices_slice])) &
                    (invoice_table.state == 'paid')),
                group_by=[invoice_table.id]))

            for k, v in cursor.fetchall():
                result[k] = v.date()
        return result

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
        if (not ServerContext().get('_payment_term_change', False) and
                not ServerContext().get('pre_commit_number', False)):
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
        if not ServerContext().get('_payment_term_change', False):
            super(Invoice, cls).update_taxes(invoices, exception)

    @classmethod
    def is_master_object(cls):
        return True

    def get_doc_template_kind(self):
        return super(Invoice, self).get_doc_template_kind() + [
            self.business_kind]

    def get_template_holders_sub_domains(self):
        res = super(Invoice, self).get_template_holders_sub_domains()
        res.append(['OR', [
                    ('kind', '!=', ''), ('kind', '=', self.business_kind)],
                [
                    ('kind', '=', '')],
                ])
        return res

    @fields.depends('state', 'amount_to_pay_today', 'total_amount')
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
        elif self.state == 'cancel' and name == 'color':
            return 'grey'
        elif (self.amount_to_pay_today > 0 or self.total_amount < 0
                or self.state == 'cancel' and name == 'form_color'):
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
        with ServerContext().set_context(_payment_term_change=True):
            previous_moves = [x.move for x in invoices]
            cls.write(invoices, {
                    'payment_term': new_term.id,
                    'move': None,
                    'invoice_date': new_invoice_date
                    })
            new_moves = []
            for invoice, move in zip(invoices, previous_moves):
                new_moves.append(invoice.get_move())
                invoice.move = new_moves[-1]
            if new_moves:
                Move.save(new_moves)
                cls.save(invoices)
            for invoice, previous_move in zip(invoices, previous_moves):
                to_post.append(previous_move.cancel())
                reconciliation = []
                for line in previous_move.lines + to_post[-1].lines:
                    if line.account != invoice.account:
                        continue
                    if line.reconciliation:
                        break
                    reconciliation.append(line)
                else:
                    if reconciliation:
                        to_reconcile.append(reconciliation)
        Move.post(new_moves + to_post)
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
