# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
import datetime

from sql import Null, Literal, Query
from sql.aggregate import Sum
from trytond.transaction import Transaction
from trytond.server_context import ServerContext
from trytond.tools import grouped_slice
from trytond.rpc import RPC
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Bool, Not
from trytond.wizard import Wizard, StateView, Button
from trytond.model import ModelView, Workflow

from trytond.modules.coog_core import utils, model, fields
from trytond.modules.premium.offered import PREMIUM_FREQUENCY

__all__ = [
    'Invoice',
    'InvoiceLine',
    'InvoiceTax',
    'InvoiceLineDetail',
    'InvoiceLineAggregates',
    'InvoiceLineAggregatesDisplay',
    'InvoiceLineAggregatesDisplayLine',
    '_STATES',
    '_DEPENDS',
    ]
_STATES = {'invisible': ~Eval('contract_invoice')}
_DEPENDS = ['contract_invoice']


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    start = fields.Function(
        fields.Date('Start Date', states=_STATES, depends=_DEPENDS),
        'get_contract_invoice_field', searcher='search_contract_invoice')
    end = fields.Function(
        fields.Date('End Date', states=_STATES, depends=_DEPENDS),
        'get_contract_invoice_field', searcher='search_contract_invoice')
    base_amount = fields.Function(
        fields.Numeric('Base amount', states=_STATES,
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits', 'contract_invoice']),
        'get_base_amount')
    contract = fields.Function(
        fields.Many2One('contract', 'Contract', states=_STATES,
            depends=_DEPENDS),
        'get_contract_invoice_field', searcher='search_contract_invoice')
    contract_invoice = fields.Function(
        fields.Many2One('contract.invoice', 'Contract Invoice', _STATES,
            _DEPENDS),
        'get_contract_invoice_field')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'),
        'get_currency_symbol')
    fees = fields.Function(
        fields.Numeric('Fees', states=_STATES,
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits', 'contract_invoice']),
        'get_fees')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._error_messages.update({
                'post_on_non_active_contract': 'Impossible to post invoice '
                '"%(invoice)s" on contract "%(contract)s" which is '
                '"%(status)s"',
                'previous_invoices_not_posted': 'There are %s invoices with '
                'a start date before %s on contract %s. Proceeding further '
                'will post those as well.\n\n\t%s',
                'future_invoices_existing': 'You cannot cancel this invoice.\n'
                'There are %(number_invoices)s invoice(s) with a start date '
                'after %(start_date)s on contract %(contract)s.'
                '\n\n\t%(invoices)s',
                })
        cls.untaxed_amount.states = {
            'invisible': Bool(Eval('contract_invoice')),
            }
        cls.untaxed_amount.depends += ['contract_invoice']
        cls._buttons.update({
                'cancel': {
                    'invisible': (~Eval('state').in_(['draft', 'validated',
                        'posted']))
                    }})
        cls.business_kind.selection += [
            ('contract_invoice', 'Contract Invoice'),
            ]
        cls.business_kind.depends += ['contract_invoice']
        cls._transitions |= {('paid', 'cancel')}

    @classmethod
    def __register__(cls, module_name):
        super(Invoice, cls).__register__(module_name)
        # Migration from 1.6 Store Bsuiness Kind
        cursor = Transaction().connection.cursor()
        invoice = cls.__table__()
        to_update = cls.__table__()
        contract_invoice = Pool().get('contract.invoice').__table__()

        query = invoice.join(contract_invoice,
            condition=contract_invoice.invoice == invoice.id
            ).select(invoice.id,
            where=((invoice.business_kind == Null)
                & (invoice.type == 'out')))
        cursor.execute(*to_update.update(
                columns=[to_update.business_kind],
                values=[Literal('contract_invoice')],
                where=to_update.id.in_(query)))

    @classmethod
    def validate(cls, *args, **kwargs):
        if ServerContext().get('disable_invoice_validation', False):
            return
        return super(Invoice, cls).validate(*args, **kwargs)

    @classmethod
    def _validate(cls, *args, **kwargs):
        if ServerContext().get('disable_invoice_validation', False):
            return
        return super(Invoice, cls)._validate(*args, **kwargs)

    @classmethod
    def view_attributes(cls):
        is_contract_type = (Bool(Eval('business_kind') == 'contract_invoice'))
        return super(Invoice, cls).view_attributes() + [
            ('//group[@id="invoice_lines"]',
                'states', {
                    'invisible': is_contract_type,
                    }),
            ('//group[@id="invoice_lines_insurance"]',
                'states', {
                    'invisible': Not(is_contract_type),
                    })
            ]

    def get_base_amount(self, name):
        return self.untaxed_amount - self.fees

    def get_taxes_included(self, name=None):
        # Insurance product do not reference tryton products, so we need to
        # store the information elsewhere and override the base taxes rules. We
        # must use `getattr` since the invoice may not be already saved
        contract = getattr(self, 'contract', None)
        business_kind = getattr(self, 'business_kind', None)
        if contract and business_kind == 'contract_invoice':
            return bool(self.contract.product.taxes_included_in_premium)
        return super(Invoice, self).get_taxes_included(name)

    @classmethod
    def get_contract_invoice_field(cls, instances, name):
        res = {}
        cursor = Transaction().connection.cursor()

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

    def get_reference_object_for_edm(self, template):
        return self.contract or super(Invoice,
            self).get_reference_object_for_edm(template)

    @classmethod
    def get_fees(cls, invoices, name):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        invoice_line = pool.get('account.invoice.line').__table__()
        invoice_line_detail = pool.get(
            'account.invoice.line.detail').__table__()
        result = {x.id: 0 for x in invoices}

        query_table = invoice_line.join(invoice_line_detail,
            condition=(invoice_line.id == invoice_line_detail.invoice_line)
            & (invoice_line_detail.fee != Null))

        for invoice_slice in grouped_slice(invoices):
            slice_clause = invoice_line.invoice.in_(
                [x.id for x in invoice_slice])
            cursor.execute(*query_table.select(invoice_line.invoice,
                    Sum(invoice_line.unit_price),
                    where=slice_clause, group_by=[invoice_line.invoice]))
            for invoice_id, total in cursor.fetchall():
                result[invoice_id] = total
        return result

    @classmethod
    def search_contract_invoice(cls, name, clause):
        target, operator, value = clause
        if operator == 'ilike' and target == 'contract':
            # Specific filter on contract  :
            # Search on rec_name causes crashe
            Contract = Pool().get('contract')
            operator = 'in'
            value = Contract.search(['rec_name', 'ilike', value], query=True)
        elif target.startswith('contract.'):
            Contract = Pool().get('contract')
            target = target[9:]
            value = Contract.search([target, operator, value], query=True)
            operator = 'in'
        Operator = fields.SQL_OPERATORS[operator]

        contract_invoice = Pool().get('contract.invoice').__table__()
        invoice = cls.__table__()

        query_table = invoice.join(contract_invoice, type_='LEFT',
            condition=(contract_invoice.invoice == invoice.id))

        if not isinstance(value, list) and not isinstance(value, Query):
            value = getattr(cls, name).sql_format(value)
        if value != []:
            query = query_table.select(invoice.id,
                where=Operator(getattr(contract_invoice, name), value))
        else:
            query = []

        return [('id', 'in', query)]

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
        Date = Pool().get('ir.date')
        if self.contract:
            if self.start and self.end:
                return '%s - %s - (%s - %s) [%s]' % (
                    self.contract.rec_name,
                    self.currency.amount_as_string(self.total_amount),
                    Date.date_as_string(self.start),
                    Date.date_as_string(self.end),
                    self.state_string)
            else:
                return '%s - %s [%s]' % (self.contract.rec_name,
                    self.currency.amount_as_string(self.total_amount),
                    self.state_string)
        else:
            if self.start and self.end:
                return '%s - %s - (%s - %s) [%s]' % (
                    self.description,
                    self.currency.amount_as_string(self.total_amount),
                    Date.date_as_string(self.start),
                    Date.date_as_string(self.end),
                    self.state_string)
            else:
                return '%s - %s [%s]' % (self.description,
                    self.currency.amount_as_string(self.total_amount),
                    self.state_string)

    def get_icon(self, name=None):
        if self.reconciled:
            return 'coopengo-reconciliation'

    def update_move_line_from_billing_information(self, line,
            billing_information):
        if self.contract and self.fees and billing_information.direct_debit:
            all_fee_in_product = True
            for cur_line in self.lines:
                if (not cur_line.detail or not cur_line.detail.fee or
                        cur_line.detail.fee not in self.contract.product.fees):
                    all_fee_in_product = False
                    break
            if all_fee_in_product:
                line.payment_date = \
                    self.contract.get_non_periodic_payment_date()
                return
        new_date = billing_information.get_direct_debit_planned_date(line)
        if new_date and (getattr(line, 'payment_date', None) or
                datetime.date.min) < new_date:
            line.payment_date = new_date

    def _get_move_line(self, date, amount):
        line = super(Invoice, self)._get_move_line(date, amount)
        line.move = self.move
        if (not self.contract or not self.contract_invoice or not line
                or self.business_kind != 'contract_invoice'):
            return line
        line.contract = self.contract.id
        contract_revision_date = max(line.maturity_date,
            utils.today(), self.contract.initial_start_date or utils.today())
        with Transaction().set_context(
                contract_revision_date=contract_revision_date):
            self.update_move_line_from_billing_information(line,
                self.contract.billing_information)
            return line

    def update_invoice_before_post(self):
        if not self.invoice_date:
            self.invoice_date = self.contract_invoice.start
        self.accounting_date = max(self.invoice_date, utils.today())
        return {
            'invoice_date': self.invoice_date,
            'accounting_date': self.accounting_date,
            }

    def check_previous_invoices_posted(self):
        old_invoices = self.__class__.search([
                ('contract', '=', self.contract.id),
                ('start', '<', self.start),
                ('state', 'in', ('draft', 'validated'))],
            order=[('start', 'ASC')])
        if old_invoices:
            self.raise_user_warning('%s_%s' % (self.contract.rec_name,
                    self.start),
                'previous_invoices_not_posted', (str(len(old_invoices)),
                    str(self.start), self.contract.rec_name,
                    '\n\t'.join([x.description for x in old_invoices])))
            return old_invoices
        return []

    def check_future_invoices_cancelled(self):
        future_invoices = self.__class__.search([
                ('contract', '=', self.contract.id),
                ('start', '>', self.start),
                ('state', '!=', 'cancel')],
            order=[('start', 'ASC')])
        if future_invoices:
            self.raise_user_error(
                'future_invoices_existing',
                {
                    'number_invoices': str(len(future_invoices)),
                    'start_date': str(self.start),
                    'contract': self.contract.rec_name,
                    'invoices': '\n\t'.join([x.description
                        for x in future_invoices]),
                })
            return future_invoices
        return []

    @classmethod
    def cancel_payments(cls, payments):
        if not payments:
            return
        for payment in payments:
            payments_per_state = defaultdict(list)
            if payment.state in ('draft', 'approved'):
                payments_per_state[payment.state].append(payment)
        Pool().get('account.payment').delete_payments_by_state(
            payments_per_state)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, invoices):
        if len(invoices) == 1 and invoices[0].contract and invoices[0].start:
            invoices[0].check_future_invoices_cancelled()
        payments = sum([list(i.payments) for i in invoices
            if i.state == 'posted'], [])
        cls.cancel_payments(payments)
        cls.auto_unreconcile(invoices)
        super(Invoice, cls).cancel(invoices)

    @classmethod
    def auto_unreconcile(cls, invoices):
        pool = Pool()
        Reconciliation = pool.get('account.move.reconciliation')
        reconciliations = []
        for invoice in invoices:
            if invoice.contract and invoice.move:
                for line in invoice.move.lines:
                    if line.reconciliation:
                        reconciliations.append(line.reconciliation)
        if reconciliations:
            Reconciliation.delete(reconciliations)

    @classmethod
    def post(cls, invoices):
        if Transaction().user != 0 and len(invoices) == 1 and \
                invoices[0].contract and invoices[0].start:
            # A user clicked the "Post" button, check that all previous
            # invoices were posted
            invoices += invoices[0].check_previous_invoices_posted()

        # Post aperiodic invoices first
        invoices = sorted(invoices, key=lambda o: o.start or datetime.date.min)
        for invoice in invoices:
            if invoice.state in ('posted', 'paid'):
                continue
            if invoice.contract and invoice.contract.status != 'active':
                contract = invoice.contract
                if contract.status == 'terminated' and (not invoice.start or (
                            invoice.start >= contract.initial_start_date and
                            invoice.end <= contract.end_date)):
                    # No problem as long as the invoice is within the contract
                    # activated period
                    continue
                if (contract.status == 'hold' and contract.sub_status and
                        not contract.sub_status.hold_billing):
                    continue
                if (invoice.contract_invoice.non_periodic and
                        contract.status not in ('quote', 'declined')):
                    continue
                cls.raise_user_error(
                    'post_on_non_active_contract', {
                        'invoice': invoice.rec_name,
                        'contract': contract.rec_name,
                        'status': contract.status_string,
                        })
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
        # Use Coog report_engine module instead
        return

    def get_cancelled_in_rebill(self):
        return self.contract_invoice.get_cancelled_in_rebill() \
            if self.contract_invoice else None


class InvoiceLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.line'
    # XXX maybe change for the description
    coverage_start = fields.Date('Start Date')
    coverage_end = fields.Date('End Date')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'),
        'get_currency_symbol')
    details = fields.One2Many('account.invoice.line.detail', 'invoice_line',
        'Details', readonly=True, size=1)
    detail = fields.Function(
        fields.Many2One('account.invoice.line.detail', 'Detail'),
        'get_detail')
    covered_element = fields.Function(
        fields.Many2One('contract.covered_element', 'Covered element'),
        'get_covered_element')
    type_ = fields.Function(
        fields.Many2One('ir.model', 'Type'),
        'get_type')

    def get_currency_symbol(self, name):
        return self.currency.symbol if self.currency else ''

    @classmethod
    def get_detail(cls, lines, name):
        result = {x.id: None for x in lines}
        cursor = Transaction().connection.cursor()
        detail_table = Pool().get('account.invoice.line.detail').__table__()

        for line_slice in grouped_slice(lines):
            cursor.execute(*detail_table.select(detail_table.invoice_line,
                    detail_table.id, where=detail_table.invoice_line.in_(
                        [x.id for x in line_slice])))

            result.update(dict(cursor.fetchall()))
        return result

    def get_type(self, name=None):
        pool = Pool()
        Model = pool.get('ir.model')
        if self.detail and self.detail.parent:
            model, = Model.search([('model', '=',
                self.detail.parent.__name__)])
            return model.id

    def get_covered_element(self, name=None):
        if not self.detail:
            return
        if self.detail.covered_element:
            return self.detail.covered_element.id
        if self.detail.option and self.detail.option.covered_element:
            return self.detail.option.covered_element.id
        if self.detail and self.detail.premium:
            covered_element = getattr(self.detail.premium.parent,
                'covered_element', None)
            if covered_element:
                return covered_element.id

    def get_move_lines(self):
        lines = super(InvoiceLine, self).get_move_lines()
        if self.invoice.contract:
            for line in lines:
                line.contract = self.invoice.contract
        return lines

    @property
    def origin_name(self):
        if self.detail:
            return self.detail.parent.rec_name
        return super(InvoiceLine, self).origin_name

    @classmethod
    def _get_origin(cls):
        return super(InvoiceLine, cls)._get_origin() + [
            'contract']


class InvoiceTax:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.tax'

    def get_move_lines(self):
        lines = super(InvoiceTax, self).get_move_lines()
        if self.invoice.contract:
            for line in lines:
                line.contract = self.invoice.contract
        return lines


class InvoiceLineDetail(model.CoogSQL, model.CoogView):
    'Invoice Line Detail'

    __name__ = 'account.invoice.line.detail'

    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
        ondelete='CASCADE', readonly=True, required=True, select=True)
    contract = fields.Many2One('contract', 'Contract', select=True,
        ondelete='RESTRICT', readonly=True)
    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', select=True, ondelete='RESTRICT', readonly=True)
    option = fields.Many2One('contract.option', 'Option', select=True,
        ondelete='RESTRICT', readonly=True)
    extra_premium = fields.Many2One('contract.option.extra_premium',
        'Extra Premium', select=True, ondelete='RESTRICT', readonly=True)
    contract_fee = fields.Many2One('contract.fee', 'Contract Fee',
        select=True, ondelete='RESTRICT', readonly=True)
    product = fields.Many2One('offered.product', 'Product', select=True,
        readonly=True, ondelete='RESTRICT')
    coverage = fields.Many2One('offered.option.description', 'Coverage',
        select=True, readonly=True, ondelete='RESTRICT')
    fee = fields.Many2One('account.fee', 'Fee', select=True,
        ondelete='RESTRICT', readonly=True)
    rate = fields.Numeric('Rate', required=True)
    frequency = fields.Selection(PREMIUM_FREQUENCY, 'Frequency', sort=False)
    taxes = fields.Char('Taxes', readonly=True)
    parent = fields.Function(
        fields.Reference('Parent Entity', 'get_parent_models'),
        'get_parent', updater='update_parent_field')
    rated_entity = fields.Function(
        fields.Reference('Rated Entity', 'get_rated_entity_models'),
        'get_rated_entity', updater='update_rated_entity_field')
    premium = fields.Many2One('contract.premium', 'Premium',
        ondelete='SET NULL', readonly=True, select=True)

    @classmethod
    def __setup__(cls):
        super(InvoiceLineDetail, cls).__setup__()
        cls.__rpc__.update({
                'get_parent_models': RPC(readonly=1),
                'get_rated_entity_models': RPC(readonly=1),
                })

    def get_parent(self, name):
        for fname in self.get_possible_parent_field():
            fvalue = getattr(self, fname)
            if fvalue:
                return '%s,%i' % (fvalue.__name__, fvalue.id)
        raise Exception('Orphan Line')

    def get_rated_entity(self, name):
        for fname in self.get_possible_rated_entity_field():
            fvalue = getattr(self, fname)
            if fvalue:
                return '%s,%i' % (fvalue.__name__, fvalue.id)
        raise Exception('Orphan Line')

    def get_rec_name(self, name):
        return '%s : %s %s' % (self.rated_entity.rec_name, self.rate,
            self.frequency)

    def update_parent_field(self, value):
        value_model = value.__name__
        not_set = True
        for fname in self.get_possible_parent_field():
            if self._fields[fname].model_name == value_model:
                setattr(self, fname, value)
                not_set = False
            else:
                setattr(self, fname, None)
        if not_set:
            raise Exception('parent field does not accept %s model as value' %
                value_model)

    def update_rated_entity_field(self, value):
        value_model = value.__name__
        not_set = True
        for fname in self.get_possible_rated_entity_field():
            if self._fields[fname].model_name == value_model:
                setattr(self, fname, value)
                not_set = False
            else:
                setattr(self, fname, None)
        if not_set:
            raise Exception('rated_entity field does not accept'
                ' %s model as value' % value_model)

    @classmethod
    def get_possible_parent_field(cls):
        return set(['contract', 'covered_element', 'option', 'extra_premium',
                'contract_fee'])

    @classmethod
    def get_parent_models(cls):
        result = []
        for field_name in cls.get_possible_parent_field():
            field = cls._fields[field_name]
            result.append((field.model_name, field.string))
        return result

    @classmethod
    def get_possible_rated_entity_field(cls):
        return ['product', 'coverage', 'fee']

    @classmethod
    def get_rated_entity_models(cls):
        result = []
        for field_name in cls.get_possible_rated_entity_field():
            field = cls._fields[field_name]
            result.append((field.model_name, field.string))
        return result

    @classmethod
    def new_detail_from_premium(cls, premium=None):
        new_detail = cls()
        if premium is None:
            return new_detail
        for fname in ('rated_entity', 'parent', 'frequency'):
            setattr(new_detail, fname, getattr(premium, fname))
        new_detail.rate = premium.amount
        new_detail.taxes = ', '.join([x.name for x in premium.taxes])
        new_detail.premium = premium
        return new_detail

    def get_option(self):
        if getattr(self, 'option', None):
            return self.option
        if getattr(self, 'extra_premium', None):
            return self.extra_premium.option


class InvoiceLineAggregates(Wizard):
    'Calculate Invoice Line Aggregates'

    __name__ = 'account.invoice.aggregate_lines'

    start_state = 'display'
    display = StateView('account.invoice.aggregate_lines.display',
        'contract_insurance_invoice.invoice_aggregate_lines_view_form', [
            Button('Ok', 'end', 'tryton-ok')])

    def default_display(self, name):
        assert Transaction().context.get('active_model') == 'account.invoice'
        invoice = Pool().get('account.invoice')(
            Transaction().context.get('active_id'))
        lines = defaultdict(lambda: {
                'base_amount': 0,
                'tax_amount': 0,
                'currency_digits': invoice.currency.digits,
                'currency_symbol': invoice.currency.symbol,
                })
        for line in invoice.lines:
            lines[line.detail.rated_entity]['base_amount'] += line.amount
            lines[line.detail.rated_entity]['tax_amount'] += line.tax_amount

        for k, v in lines.iteritems():
            v['rated_entity'] = k.rec_name
            v['total_amount'] = v['base_amount'] + v['tax_amount']

        def order_lines(key):
            # Weird order method, tries to ensure lines are ordered as follows:
            #   - Product lines first
            #   - Then coverage lines
            #   - Then fees
            #   - Then others
            if key.__name__ == 'account.fee':
                return '5_' + key.rec_name
            if key.__name__ == 'offered.option.description':
                return '3_' + key.rec_name
            if key.__name__ == 'offered.product':
                return '1_' + key.rec_name
            return '9_' + key.rec_name

        return {
            'lines': [lines[x] for x in sorted(lines.keys(),
                    key=order_lines)]}


class InvoiceLineAggregatesDisplay(model.CoogView):
    'Display Invoice Line Aggregates'

    __name__ = 'account.invoice.aggregate_lines.display'

    lines = fields.One2Many('account.invoice.aggregate_lines.display.line',
        None, 'Lines', readonly=True)


class InvoiceLineAggregatesDisplayLine(model.CoogView):
    'Invoice Line Aggregates Displayer'

    __name__ = 'account.invoice.aggregate_lines.display.line'

    rated_entity = fields.Char('Rated Entity')
    base_amount = fields.Numeric('Base Amount', digits=(16,
            Eval('currency_digits', 2)), readonly=True,
        depends=['currency_digits'])
    tax_amount = fields.Numeric('Tax Amount', digits=(16,
            Eval('currency_digits', 2)), readonly=True,
        depends=['currency_digits'])
    total_amount = fields.Numeric('Total Amount', digits=(16,
            Eval('currency_digits', 2)), readonly=True,
        depends=['currency_digits'])
    currency_digits = fields.Integer('Currency Digits',
        states={'invisible': True})
    currency_symbol = fields.Char('Currency Symbol', readonly=True)
