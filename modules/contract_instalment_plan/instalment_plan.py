# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta

from trytond.model import Workflow
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.server_context import ServerContext

from trytond.modules.coog_core import model, fields, coog_date, utils

__all__ = [
    'ContractInstalmentPlan',
    'ContractInstalmentPlanPayment',
    ]

CALCULATION_METHOD = [
    ('manual', 'Manual'),
    ('based_on_frequency', 'Based On Frequency'),
    ]
PAYMENT_FREQUENCY = [
    ('1', 'Monthly'),
    ('2', 'Bimonthly'),
    ('3', 'Quarterly'),
    ('6', 'Half yearly'),
    ('12', 'Yearly'),
    ]


class ContractInstalmentPlan(Workflow, model.CoogSQL, model.CoogView):
    'Contract Instalment Plan'

    __metaclass__ = PoolMeta
    __name__ = 'contract.instalment_plan'
    _func_key = 'rec_name'

    state = fields.Selection([
            ('draft', 'Draft'),
            ('validated', 'Validated'),
            ('cancel', 'Canceled'),
            ], 'State', readonly=True)
    state_string = state.translated('state')
    scheduled_payments = fields.One2Many('contract.instalment_plan.payment',
        'instalment', 'Scheduled Payments', order=[('maturity_date', 'ASC')],
        readonly=True, delete_missing=True)
    contract = fields.Many2One('contract', 'Contract', required=True,
        ondelete='CASCADE', select=True)
    company = fields.Function(
        fields.Many2One('company.company', 'Company', required=True),
        'get_company')
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'get_currency')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'get_currency_digits')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'),
        'get_currency_symbol')
    total_amount = fields.Numeric('Total Amount',
        states={'required': Eval('state') != 'draft'},
        digits=(16, Eval('currency_digits', 2)),
        readonly=True, select=True, depends=['state', 'currency_digits'])
    invoice_period_start = fields.Date('Invoices Period Start', required=True)
    invoice_period_end = fields.Date('Invoice Period End', required=True)
    color = fields.Function(
        fields.Char('Color'), 'get_color')

    @classmethod
    def __setup__(cls):
        super(ContractInstalmentPlan, cls).__setup__()
        cls._error_messages.update({
                'delete_draft': ('Instalment Plan "%(instalment)s" must be in '
                    'draft before deletion.'),
                'missing_period_data': ('Contract and invoice period dates are '
                    'required.'),
                'invoice_period_inconsistent': ('Invoice period end '
                    '%(end_date)s should be greater than invoices period start'
                    ' %(start_date)s.'),
                'start_date_is_not_invoicing_date': ('Invoices period start is '
                    'not valid.'),
                'end_date_is_not_invoicing_date': ('Invoice period end is '
                    'not valid.'),
                'duplicate_instalments': ('Existing instalment(s) for this '
                    'period: %(existing_instalment)s'),
                'unknown_calculation_method': ('Unknown calculation method: '
                    '%(calculation_method)s'),
                'invalid_total_amounts': ('Total amount %(total_amount)s should'
                    ' be equal to the sum of scheduled payments '
                    '%(scheduled_amount)s'),
                'paid_invoices': ('Some invoices are already paid in the '
                    'period: %(paid_invoices)s'),
                })
        cls._transitions |= set((
                ('draft', 'validated'),
                ('draft', 'cancel'),
                ('validated', 'cancel'),
                ))
        cls._buttons.update({
                'validate_instalment': {
                    'invisible': Eval('state') != 'draft',
                    'icon': 'tryton-ok',
                    },
                'draft': {
                    'invisible': True,
                    'icon': 'tryton-go-previous',
                    },
                'cancel': {
                    'readonly': Eval('state') == 'cancel',
                    'icon': 'tryton-cancel',
                    },
                'validate_instalment_plan': {
                    'invisible': ~Eval('state').in_(['draft']),
                    'icon': 'tryton-ok',
                    },
                })

    @classmethod
    def view_attributes(cls):
        return super(ContractInstalmentPlan, cls).view_attributes() + [
            ('/tree', 'colors', Eval('color')),
            ]

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        if Transaction().context.get('company', None):
            company = Company(Transaction().context.get('company'))
            return company.currency.id

    @staticmethod
    def default_company():
        return Transaction().context.get('company', None)

    @staticmethod
    def default_contract():
        # TODO get contract from domain
        return None

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        if Transaction().context.get('company', None):
            company = Company(Transaction().context.get('company'))
            return company.currency.digits
        return 2

    @staticmethod
    def default_currency_symbol():
        Company = Pool().get('company.company')
        if Transaction().context.get('company', None):
            company = Company(Transaction().context.get('company'))
            return company.currency.symbol
        return ''

    @fields.depends('contract')
    def on_change_with_company(self, name=None):
        if self.contract:
            return self.contract.company.id

    @fields.depends('company', 'contract')
    def on_change_with_currency(self, name=None):
        if self.company:
            return self.company.currency

    @fields.depends('currency', 'contract')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @fields.depends('currency', 'contract')
    def on_change_with_currency_symbol(self, name=None):
        return self.currency.symbol if self.currency else ''

    @classmethod
    def calculate_invoice_period_start(cls, contract, invoice_period_start,
            invoice_period_end):
        """
        Return the expected invoices period start for the given contract.
        If an invoices period start date (or an invoice period end date) is
        provided, the returned value is the start date of the period containing
        this date.
        If no date is provided, the returned value is the start date of the next
        period to invoice (or the last invoiced period if all the periods of the
        contract are invoiced)
        This method is called by the instalment plan management wizard.

        """
        if not contract:
            return None
        start = invoice_period_start or invoice_period_end
        if not start:
            start = contract.last_invoice_end
            if start:
                if contract.end_date and (contract.end_date <= start):
                    return contract.last_invoice_start
                else:
                    return start + relativedelta(days=+1)
        if not start:
            return contract.start_date
        periods = contract.get_invoice_periods(start, None, True)
        if periods:
            return periods[-1][0]
        return None

    @fields.depends('contract', 'invoice_period_start', 'invoice_period_end',
        'state')
    def on_change_with_invoice_period_start(self, name=None):
        if not self.state == 'draft':
            return self.invoice_period_start
        return self.__class__.calculate_invoice_period_start(self.contract,
            self.invoice_period_start, self.invoice_period_end)

    @classmethod
    def calculate_invoice_period_end(cls, contract, invoice_period_start,
            invoice_period_end):
        """
        Return the expected invoice period end for the given contract.
        If an invoice period end date (or an invoices period start date) is
        provided, the returned value is the end date of the period containing
        this date.
        If no date is provided, the returned value is the end date of the next
        period to invoice (or the last invoiced period if all the periods of the
        contract are invoiced)
        This method is called by the instalment plan management wizard.

        """
        if not contract:
            return None
        end = invoice_period_end or invoice_period_start
        if not end:
            end = contract.last_invoice_end
            if end:
                if contract.end_date and (contract.end_date <=
                        end):
                    return end
                else:
                    end = end + relativedelta(days=+1)
        if not end:
            end = contract.start_date
        periods = contract.get_invoice_periods(end, end, True)
        if periods:
            return periods[-1][1]
        return None

    @fields.depends('contract', 'invoice_period_start', 'invoice_period_end',
        'state')
    def on_change_with_invoice_period_end(self, name=None):
        if not self.state == 'draft':
            return self.invoice_period_end
        return self.__class__.calculate_invoice_period_end(self.contract,
            self.invoice_period_start, self.invoice_period_end)

    @classmethod
    def calculate_total_amount(cls, contract, invoice_period_start,
            invoice_period_end):
        """
        Return the total amount to be invoiced for the given contract on the
        given period.
        All parameters are mandatory.
        This method is called by the instalment plan management wizard.

        """
        if not all([contract, invoice_period_start, invoice_period_end]):
            return None
        if invoice_period_start > invoice_period_end:
            return None
        invoices = contract.__class__.get_future_invoices(contract,
            invoice_period_start, invoice_period_end)
        return sum([invoice.get('total_amount', 0.0) for invoice in invoices])

    @fields.depends('contract', 'invoice_period_start', 'invoice_period_end',
        'state', 'total_amount')
    def on_change_with_total_amount(self, name=None):
        if not self.state == 'draft':
            return self.total_amount
        my_class = self.__class__
        start = self.invoice_period_start \
            or my_class.calculate_invoice_period_start(self.contract,
                self.invoice_period_start, self.invoice_period_end)
        end = self.invoice_period_end \
            or my_class.calculate_invoice_period_end(self.contract,
                self.invoice_period_start, self.invoice_period_end)
        return my_class.calculate_total_amount(self.contract, start, end)

    @classmethod
    def get_color(cls, instalments, name=None):
        colors = {
            'draft': 'black',
            'validated': 'green',
            'cancel': 'grey'
            }
        return {x.id: colors[x.state] for x in instalments}

    @classmethod
    def get_company(cls, instalments, name=None):
        return {x.id: x.contract.company if x.contract else None
            for x in instalments}

    @classmethod
    def get_currency(cls, instalments, name=None):
        return {x.id: x.company.currency if x.company else None
            for x in instalments}

    @classmethod
    def get_currency_symbol(cls, instalments, name=None):
        return {x.id: x.currency.symbol if x.currency else ''
            for x in instalments}

    @classmethod
    def get_currency_digits(cls, instalments, name=None):
        return {x.id: x.currency.digits if x.currency else 2
            for x in instalments}

    def get_rec_name(self, name=None):
        return '%(contract)s [%(start_date)s - %(end_date)s]' % {
            'contract': self.contract.contract_number if self.contract else '',
            'start_date': self.invoice_period_start,
            'end_date': self.invoice_period_end}

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            [('contract.contract_number',) + tuple(clause[1:])],
            [('invoice_period_start',) + tuple(clause[1:])],
            [('invoice_period_end',) + tuple(clause[1:])],
            ]

    @classmethod
    def delete(cls, instalments):
        for instalment in instalments:
            if instalment.state != 'draft':
                cls.raise_user_error('delete_draft', {
                        'instalment': instalment.rec_name})
        super(ContractInstalmentPlan, cls).delete(instalments)

    @classmethod
    @model.CoogView.button
    @Workflow.transition('draft')
    def draft(cls, instalments):
        pass

    @classmethod
    @model.CoogView.button
    @Workflow.transition('validated')
    def validate_instalment(cls, instalments):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ContractInvoice = pool.get('contract.invoice')
        PaymentTerm = pool.get('account.invoice.payment_term')
        for instalment in instalments:
            contract = instalment.contract
            invoice_start = instalment.invoice_period_start
            invoice_end = instalment.invoice_period_end
            # check instalment can be validated
            cls.check_period(contract, invoice_start, invoice_end, instalment)
            instalment.check_amounts()
            # search existing invoices
            invoice = Invoice.__table__()
            contract_invoice = ContractInvoice.__table__()
            where_clause = (
                (contract_invoice.contract == contract.id) &
                (invoice.state != 'cancel') &
                (contract_invoice.start <= invoice_end) &
                (contract_invoice.end >= invoice_start))
            cursor = Transaction().connection.cursor()
            cursor.execute(*invoice.join(contract_invoice, condition=(
                        contract_invoice.invoice == invoice.id)).select(
                    invoice.id, contract_invoice.start, contract_invoice.end,
                    where=where_clause, order_by=contract_invoice.start))
            START, END = [1, 2]
            invoices = cursor.fetchall()
            # rebill out of period invoices
            first_invoice_start = min(invoices[0][START] if invoices else
                invoice_start, invoice_start)
            to_invoice_start = invoices[-1][END] if invoices else invoice_start
            last_invoice_end = max(to_invoice_start, invoice_end)
            if first_invoice_start < invoice_start:
                contract.rebill(first_invoice_start, invoice_start +
                    relativedelta(day=-1))
            if invoice_end < last_invoice_end:
                contract.rebill(invoice_end + relativedelta(day=+1),
                    last_invoice_end)
                to_invoice_start = invoices[-1][START] if invoices else None
            # change_term of existing invoices
            existing_invoices = Invoice.browse([x[0] for x in invoices if (
                        x[1] >= invoice_start and x[2] <= invoice_end)])
            Invoice.write(existing_invoices, {'instalment_plan': instalment.id})
            instalment_payment_term = PaymentTerm.search([
                    ('based_on_instalment', '=', True),
                    ('active', '=', True)])[0]
            if existing_invoices:
                to_change_term = [i for i in existing_invoices if
                    (i.state == 'posted')]
                Invoice.change_term(to_change_term, instalment_payment_term,
                    utils.today())
                to_change_payment_condition = [i for i in existing_invoices if
                    (i.state != 'posted')]
                Invoice.write(to_change_payment_condition, {
                    'payment_term': instalment_payment_term.id})
            # invoice missing invoices
            if invoice_end > to_invoice_start:
                with ServerContext().set_context(
                        payment_term=instalment_payment_term,
                        instalment=instalment):
                    contract.invoice([contract], invoice_end)

    @classmethod
    @model.CoogView.button
    @Workflow.transition('cancel')
    def cancel(cls, instalments):
        to_delete = [x for x in instalments if x.state == 'draft']
        if to_delete:
            cls.delete(to_delete)

    @classmethod
    @model.CoogView.button_action(
        'contract_instalment_plan.act_validate_instalment_plan')
    def validate_instalment_plan(cls, instalments):
        pass

    @classmethod
    def check_period(cls, contract, invoice_period_start, invoice_period_end,
            instalment=None, raise_error=True):
        if not all([contract, invoice_period_end, invoice_period_start]):
            if raise_error:
                cls.raise_user_error('missing_period_data')
            return False
        if invoice_period_start > invoice_period_end:
            if raise_error:
                cls.raise_user_error('invoice_period_inconsistent', {
                        'start_date': invoice_period_start,
                        'end_date': invoice_period_end})
            return False
        start_period = contract.get_invoice_periods(invoice_period_start, None,
            True)
        if not start_period or (start_period[-1][0] != invoice_period_start):
            if raise_error:
                cls.raise_user_error('start_date_is_not_invoicing_date')
            return False
        end_period = contract.get_invoice_periods(invoice_period_end,
            invoice_period_end, True)
        if not end_period or (end_period[-1][1] != invoice_period_end):
            if raise_error:
                cls.raise_user_error('end_date_is_not_invoicing_date')
            return False
        InstalmentPlan = Pool().get('contract.instalment_plan')
        clause = [
            ('contract', '=', contract.id),
            ('state', '!=', ['cancel']),
            ('invoice_period_end', '>=', invoice_period_start),
            ('invoice_period_start', '<=', invoice_period_end),
            ]
        if instalment:
            clause.append(('id', '!=', instalment.id))
        duplicate_instalments = InstalmentPlan.search(clause)
        if duplicate_instalments:
            if raise_error:
                cls.raise_user_error('duplicate_instalments',
                    {'existing_instalment': ', '.join([x.rec_name for x
                                in duplicate_instalments])})
            return False
        paid_invoices = cls.get_invoices(contract, invoice_period_start,
            invoice_period_end, ['paid'])
        if paid_invoices:
            if raise_error:
                cls.raise_user_error('paid_invoices',
                    {'paid_invoices': ', '.join(
                            [x.rec_name for x in paid_invoices])})
            return False
        return True

    def check_amounts(self):
        sum_amount = sum([x.amount for x in self.scheduled_payments])
        if not self.total_amount or (self.total_amount != sum_amount):
            self.raise_user_error('invalid_total_amounts', {
                    'total_amount': self.total_amount,
                    'scheduled_amount': sum_amount
                    })

    @classmethod
    def do_calculate(cls, contract, invoice_period_start, invoice_period_end,
            method='manual', **kwargs):
        if method not in [x[0] for x in CALCULATION_METHOD]:
            cls.raise_user_error('unknown_calculation_method', {
                    'calculation_method': method})
        if not all([contract, invoice_period_end, invoice_period_start]):
            cls.raise_user_error('missing_period_data')
        pool = Pool()
        InstalmentPayment = pool.get('contract.instalment_plan.payment')
        payments = []
        if method == 'manual':
            if kwargs.get('init_from_invoices', False):
                invoices = contract.get_future_invoices(contract,
                    invoice_period_start, invoice_period_end)
                payments = [{
                        'maturity_date': x.get('start'),
                        'amount': x.get('total_amount', 0.00),
                        'currency': cls.default_currency(),
                        'currency_digits': cls.default_currency_digits(),
                        'currency_symbol': cls.default_currency_symbol()}
                    for x in invoices]
                payments = [InstalmentPayment(**p) for p in payments]
        elif method == 'based_on_frequency':
            start_date = kwargs.get('start_date', invoice_period_start)
            frequency = kwargs.get('frequency',
                PAYMENT_FREQUENCY[0][0])
            nb_payments = kwargs.get('nb_payments',
                len(contract.get_invoice_periods(invoice_period_start,
                    invoice_period_end, True)))
            assert nb_payments > 0
            assert frequency in [x[0] for x in PAYMENT_FREQUENCY]
            frequency = int(frequency)
            total_amount = cls.calculate_total_amount(contract,
                invoice_period_start, invoice_period_end)
            period_amount = contract.get_currency().round(
                total_amount / nb_payments)
            last_period_amount = total_amount - \
                (nb_payments - 1) * period_amount
            payments = [{
                    'maturity_date': coog_date.add_month(start_date,
                        i * frequency),
                    'amount': period_amount,
                    'currency': cls.default_currency(),
                    'currency_digits': cls.default_currency_digits(),
                    'currency_symbol': cls.default_currency_symbol()}
                for i in xrange(nb_payments - 1)]
            payments.append({
                    'maturity_date': coog_date.add_month(start_date,
                        frequency * (nb_payments - 1)),
                    'amount': last_period_amount,
                    'currency': cls.default_currency(),
                    'currency_digits': cls.default_currency_digits(),
                    'currency_symbol': cls.default_currency_symbol()})
            payments = [InstalmentPayment(**p) for p in payments]
        return payments

    @classmethod
    def get_invoices(cls, contract, start_date, end_date, statuses=None):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ContractInvoice = pool.get('contract.invoice')
        invoice = Invoice.__table__()
        contract_invoice = ContractInvoice.__table__()
        where_clause = (
            (contract_invoice.contract == contract.id) &
            (contract_invoice.start <= end_date) &
            (contract_invoice.end >= start_date))
        if statuses:
            where_clause = where_clause & (invoice.state.in_(statuses))
        else:
            where_clause = where_clause & (invoice.state != 'cancel')
        cursor = Transaction().connection.cursor()
        cursor.execute(*invoice.join(contract_invoice, condition=(
                    contract_invoice.invoice == invoice.id)).select(
                invoice.id, where=where_clause,
                order_by=contract_invoice.start))
        return Invoice.browse([x[0] for x in cursor.fetchall()])


class ContractInstalmentPlanPayment(model.CoogSQL, model.CoogView):
    'Scheduled Payment'

    __metaclass__ = PoolMeta
    __name__ = 'contract.instalment_plan.payment'

    instalment = fields.Many2One('contract.instalment_plan', 'Instalment Plan',
        ondelete='CASCADE', select=True, required=True)
    amount = fields.Numeric('Amount', required=True,
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    maturity_date = fields.Date('Maturity Date', required=True)
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'), 'get_currency_symbol')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'), 'get_currency_digits')

    @classmethod
    def get_currency_symbol(cls, payments, name=None):
        return {x.id: x.instalment.currency_symbol for x in payments}

    @classmethod
    def get_currency_digits(cls, payments, name=None):
        return {x.id: x.instalment.currency_digits for x in payments}
