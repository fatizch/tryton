from sql.aggregate import Sum, Max
from sql.operators import Concat

from trytond.transaction import Transaction
from trytond.tools import grouped_slice
from trytond.rpc import RPC
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import coop_string, utils, model, fields
from trytond.modules.premium.offered import PREMIUM_FREQUENCY

__metaclass__ = PoolMeta
__all__ = [
    'Invoice',
    'InvoiceLine',
    'InvoiceLineDetail',
    '_STATES',
    '_DEPENDS',
    ]
_STATES = {'invisible': ~Eval('contract_invoice')}
_DEPENDS = ['contract_invoice']


class Invoice:
    __name__ = 'account.invoice'

    start = fields.Function(
        fields.Date('Start Date', states=_STATES, depends=_DEPENDS),
        'get_contract_invoice_field', searcher='search_contract_invoice')
    end = fields.Function(
        fields.Date('End Date', states=_STATES, depends=_DEPENDS),
        'get_contract_invoice_field', searcher='search_contract_invoice')
    base_amount = fields.Function(
        fields.Numeric('Base amount', states=_STATES, depends=_DEPENDS),
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
        fields.Numeric('Fees', states=_STATES, depends=_DEPENDS),
        'get_fees')
    reconciliation_date = fields.Function(
        fields.Date('Reconciliation Date',
            states={'invisible': ~Eval('reconciliation_date')}),
        'get_reconciliation_date')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._error_messages.update({
                'post_on_non_active_contract': 'Impossible to post invoice '
                '"%(invoice)s" on contract "%(contract)s" which is '
                '"%(status)s"',
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
        cls.business_type.selection += [
            ('contract_invoice', 'Contract Invoice'),
            ]
        cls.business_type.depends += ['contract_invoice']

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
        invoice_line = pool.get('account.invoice.line').__table__()
        invoice_line_detail = pool.get(
            'account.invoice.line.detail').__table__()
        result = {x.id: 0 for x in invoices}

        query_table = invoice_line.join(invoice_line_detail,
            condition=(invoice_line.id == invoice_line_detail.invoice_line)
            & (invoice_line_detail.fee != None))

        for invoice_slice in grouped_slice(invoices):
            slice_clause = invoice_line.invoice.in_(
                [x.id for x in invoice_slice])
            cursor.execute(*query_table.select(invoice_line.invoice,
                    Sum(invoice_line.unit_price),
                    where=slice_clause, group_by=[invoice_line.invoice]))
            for invoice_id, total in cursor.fetchall():
                result[invoice_id] = total
        return result

    def get_business_type(self, name):
        if self.contract_invoice:
            return 'contract_invoice'
        else:
            return super(Invoice, self).get_business_type(name)

    @classmethod
    def search_contract_invoice(cls, name, clause):
        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]

        contract_invoice = Pool().get('contract.invoice').__table__()
        invoice = cls.__table__()

        query_table = invoice.join(contract_invoice, type_='LEFT',
            condition=(contract_invoice.invoice == invoice.id))

        query = query_table.select(invoice.id,
                where=Operator(getattr(contract_invoice, name),
                    getattr(cls, name).sql_format(value)))

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
                    coop_string.translate_value(self, 'state'))
            else:
                return '%s - %s [%s]' % (self.contract.rec_name,
                    self.currency.amount_as_string(self.total_amount),
                    coop_string.translate_value(self, 'state'))
        else:
            if self.start and self.end:
                return '%s - %s - (%s - %s) [%s]' % (
                    self.description,
                    self.currency.amount_as_string(self.total_amount),
                    Date.date_as_string(self.start),
                    Date.date_as_string(self.end),
                    coop_string.translate_value(self, 'state'))
            else:
                return '%s - %s [%s]' % (self.description,
                    self.currency.amount_as_string(self.total_amount),
                    coop_string.translate_value(self, 'state'))

    def get_icon(self, name=None):
        if self.reconciled:
            return 'coopengo-reconciliation'

    def update_move_line_from_billing_information(self, line,
            billing_information):
        return {'payment_date':
            billing_information.get_direct_debit_planned_date(line)}

    def _get_move_line_invoice_line(self):
        res = super(Invoice, self)._get_move_line_invoice_line()
        if not self.contract:
            return res
        for line in res:
            line['contract'] = self.contract
        return res

    def _get_move_line_invoice_tax(self):
        res = super(Invoice, self)._get_move_line_invoice_tax()
        if not self.contract:
            return res
        for line in res:
            line['contract'] = self.contract
        return res

    def _get_move_line(self, date, amount):
        line = super(Invoice, self)._get_move_line(date, amount)
        if not self.contract or not self.contract_invoice or not line:
            return line
        line['contract'] = self.contract.id
        contract_revision_date = max(line['maturity_date'],
            utils.today())
        with Transaction().set_context(
                contract_revision_date=contract_revision_date):
            res = self.update_move_line_from_billing_information(
                line, self.contract.billing_information)
            line.update(res)
            return line

    def update_invoice_before_post(self):
        if not self.invoice_date:
            self.invoice_date = self.contract_invoice.start
        self.accounting_date = max(self.invoice_date, utils.today())
        return {
            'invoice_date': self.invoice_date,
            'accounting_date': self.accounting_date,
            }

    @classmethod
    def post(cls, invoices):
        for invoice in invoices:
            if invoice.state in ('posted', 'paid'):
                continue
            if invoice.contract and invoice.contract.status not in ('active'
                    'terminated'):
                cls.raise_user_error(
                    'post_on_non_active_contract', {
                        'invoice': invoice.rec_name,
                        'contract': invoice.contract.rec_name,
                        'status': invoice.contract.status_string,
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

    @classmethod
    def get_reconciliation_date(cls, invoices, name):
        pool = Pool()
        cursor = Transaction().cursor
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
                    move.origin == Concat(cls.__name__ + ',',
                        invoice_table.id)))

            cursor.execute(*query_table.select(invoice_table.id,
                Max(reconciliation.create_date),
                where=((invoice_table.id.in_([x.id for x in invoices_slice])) &
                    (invoice_table.state == 'paid')),
                group_by=[invoice_table.id]))

            for k, v in cursor.fetchall():
                result[k] = v.date()
        return result

    def _get_tax_context(self):
        context = super(Invoice, self)._get_tax_context()
        if (getattr(self, 'contract', None) and self.contract.product and
                self.contract.product.taxes_included_in_premium):
            context['tax_included'] = True
        return context

    def _round_taxes(self, taxes):
        '''
            Tax included option is only available if taxes are rounded per line
            This code implements the Sum Preserving Rounding algorithm
        '''
        context = Transaction().context
        if not context.get('tax_included') or not context['tax_included']:
            return super(Invoice, self)._round_taxes(taxes)
        if not self.currency:
            return
        expected_amount_non_rounded = 0
        sum_of_rounded = 0
        for taxline in taxes.itervalues():
            if expected_amount_non_rounded == 0:
                # Add base amount only for the first tax
                expected_amount_non_rounded = taxline['base']
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


class InvoiceLine:
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
        cursor = Transaction().cursor
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
        if self.detail and self.detail.premium:
            covered_element = getattr(self.detail.premium.parent,
                'covered_element', None)
            if covered_element:
                return covered_element.id

    @property
    def origin_name(self):
        if self.detail:
            return self.detail.parent.rec_name
        return super(InvoiceLine, self).origin_name

    @classmethod
    def _get_origin(cls):
        return super(InvoiceLine, cls)._get_origin() + [
            'contract']


class InvoiceLineDetail(model.CoopSQL, model.CoopView):
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
        'get_parent', 'set_reference_field')
    rated_entity = fields.Function(
        fields.Reference('Rated Entity', 'get_rated_entity_models'),
        'get_rated_entity', 'set_reference_field')
    premium = fields.Many2One('contract.premium', 'Premium',
        ondelete='SET NULL', readonly=True)

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

    @classmethod
    def set_reference_field(cls, detail_ids, name, value):
        value_model, value_id = value.split(',')
        for fname in getattr(cls, 'get_possible_%s_field' % name)():
            if cls._fields[fname].model_name == value_model:
                break
        else:
            raise Exception('%s field does not accept %s model as value' % (
                    name, value_model))
        for detail_slice in grouped_slice(detail_ids):
            cls.write(cls.browse(detail_slice), {fname: value_id})

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
