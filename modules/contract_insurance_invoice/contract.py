import datetime
import calendar
from collections import defaultdict
from decimal import Decimal

from sql import Column, Null, Literal
from sql.aggregate import Max, Count, Sum
from sql.conditionals import Coalesce

from dateutil.rrule import rrule, rruleset, MONTHLY, DAILY
from dateutil.relativedelta import relativedelta

from trytond.pool import Pool, PoolMeta
from trytond.model import dualmethod
from trytond.pyson import Eval, And, Len, If, Bool
from trytond.error import UserError
from trytond import backend
from trytond.transaction import Transaction
from trytond.tools import reduce_ids, grouped_slice
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.rpc import RPC
from trytond.cache import Cache

from trytond.modules.cog_utils import (coop_date, coop_string, utils, model,
    fields)
from trytond.modules.contract import _STATES

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractFee',
    'ContractOption',
    'ExtraPremium',
    'ContractBillingInformation',
    'Premium',
    'ContractInvoice',
    'InvoiceContract',
    'InvoiceContractStart',
    'DisplayContractPremium',
    ]

FREQUENCIES = [
    ('once_per_contract', 'Once Per Contract'),
    ('monthly', 'Monthly'),
    ('quarterly', 'Quarterly'),
    ('half_yearly', 'Half-yearly'),
    ('yearly', 'Yearly'),
    ]


class Contract:
    __name__ = 'contract'

    invoices = fields.One2Many('contract.invoice', 'contract', 'Invoices',
        delete_missing=True)
    due_invoices = fields.Function(
        fields.One2Many('contract.invoice', None, 'Due Invoices'),
        'get_due_invoices')
    receivable_today = fields.Function(
        fields.Numeric('Receivable Today',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_receivable_today')
    payment_term = fields.Function(fields.Many2One(
        'account.invoice.payment_term', 'Payment Term'),
        'get_billing_information')
    billing_mode = fields.Function(
        fields.Many2One('offered.billing_mode', 'Billing Mode'),
        'get_billing_information')
    billing_information = fields.Function(
        fields.Many2One('contract.billing_information',
            'Current Billing Information'), 'get_billing_information')
    billing_informations = fields.One2Many('contract.billing_information',
        'contract', 'Billing Information',
        domain=[
            ('billing_mode.products', '=', Eval('product')),
            If(Bool(Eval('subscriber', False)),
                ['OR',
                    ('direct_debit_account.owners', '=', Eval('subscriber')),
                    If(Bool(Eval('id', False)),
                        [('id', 'not in', Eval('valid_billing_informations'))],
                        []),
                    ('direct_debit_account', '=', None)],
                [('direct_debit_account', '=', None)]),
            If(Bool(Eval('status') == 'active'),
                ['OR',
                    ('direct_debit', '=', False),
                    ('direct_debit_account', '!=', None)],
                [])
        ], delete_missing=True,
        states=_STATES, depends=['product', 'subscriber', 'status',
            'valid_billing_informations', 'id'])
    valid_billing_informations = fields.Function(
        fields.One2Many('contract.billing_information', None,
            'Valid Billing Informations'),
        'get_valid_billing_informations')
    last_invoice_start = fields.Function(
        fields.Date('Last Invoice Start Date'), 'get_last_invoice',
        searcher='search_last_invoice')
    last_invoice_end = fields.Function(
        fields.Date('Last Invoice End Date'), 'get_last_invoice',
        searcher='search_last_invoice')
    last_posted_invoice_end = fields.Function(
        fields.Date('Last Post Invoice End Date'), 'get_last_invoice',
        searcher='search_last_invoice')
    last_paid_invoice_end = fields.Function(
        fields.Date('Last Paid Invoice End Date'), 'get_last_invoice',
        searcher='search_last_invoice')
    account_invoices = fields.Many2Many('contract.invoice', 'contract',
        'invoice', 'Invoices', order=[('start', 'ASC')], readonly=True)
    current_term_invoices = fields.Function(
        fields.One2Many('contract.invoice', None, 'Current Term Invoices'),
        'get_current_term_invoices')
    balance = fields.Function(
        fields.Numeric('Balance', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_balance', searcher='search_balance')
    balance_today = fields.Function(
        fields.Numeric('Balance Today',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_balance_today', searcher='search_balance_today')

    _invoices_cache = Cache('invoices_report')

    @classmethod
    def _export_skips(cls):
        return (super(Contract, cls)._export_skips() |
            set(['invoices', 'account_invoices']))

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls.__rpc__.update({'ws_rate_contracts': RPC(readonly=False)})
        cls._buttons.update({
                'first_invoice': {},
                })

    @fields.depends('subscriber', 'billing_informations')
    def on_change_subscriber(self):
        if not self.billing_informations:
            return
        new_billing_information = self.billing_informations[-1]
        new_billing_information.date = None
        if new_billing_information.direct_debit_account:
            if (self.subscriber not in
                    new_billing_information.direct_debit_account.owners):
                new_billing_information.direct_debit_account = None
        self.billing_informations = [new_billing_information]

    def get_current_term_invoices(self, name):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        return [x.id for x in ContractInvoice.search([
                    ('contract', '=', self),
                    ('invoice.state', 'not in', ('cancel', 'paid')),
                    ('start', '>=', self.start_date),
                    ('end', '<=', self.end_date or datetime.date.max),
                    ])]

    @classmethod
    def get_balance(cls, contracts, name, date=None):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Account = pool.get('account.account')
        User = pool.get('res.user')
        cursor = Transaction().cursor

        line = MoveLine.__table__()
        account = Account.__table__()

        result = dict((c.id, Decimal('0.0')) for c in contracts)

        user = User(Transaction().user)
        if not user.company:
            return result
        company_id = user.company.id

        line_query, _ = MoveLine.query_get(line)

        date_clause = Literal(True)
        if date:
            date_clause = ((line.maturity_date <= date)
                | (line.maturity_date == Null))

        balance = (Sum(Coalesce(line.debit, 0)) -
            Sum(Coalesce(line.credit, 0)))
        for sub_contracts in grouped_slice(contracts):
            sub_ids = [c.id for c in sub_contracts]
            contract_where = reduce_ids(line.contract, sub_ids)
            cursor.execute(*line.join(account,
                    condition=account.id == line.account
                    ).select(line.contract, balance,
                    where=(account.active
                        & (account.kind == 'receivable')
                        & (line.reconciliation == Null)
                        & (account.company == company_id)
                        & line_query
                        & contract_where
                        & date_clause),
                    group_by=line.contract))
            for contract, balance in cursor.fetchall():
                balance = balance or 0
                # SQLite uses float for SUM
                if not isinstance(balance, Decimal):
                    balance = Decimal(str(balance))
                result[contract] = balance
        return result

    @classmethod
    def search_balance(cls, name, clause, date=None):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Account = pool.get('account.account')
        User = pool.get('res.user')

        line = MoveLine.__table__()
        account = Account.__table__()

        user = User(Transaction().user)
        if not user.company:
            return []
        company_id = user.company.id

        date_clause = Literal(True)
        if date:
            date_clause = ((line.maturity_date <= date)
                | (line.maturity_date == Null))

        line_query, _ = MoveLine.query_get(line)
        Operator = fields.SQL_OPERATORS[clause[1]]

        query = line.join(account, condition=account.id == line.account
                ).select(line.contract,
                    where=account.active
                    & (account.kind == 'receivable')
                    & (line.contract != Null)
                    & (line.reconciliation == Null)
                    & (account.company == company_id)
                    & line_query & date_clause,
                    group_by=line.contract,
                    having=Operator(Sum(Coalesce(line.debit, 0)) -
                        Sum(Coalesce(line.credit, 0)),
                        Decimal(clause[2] or 0)))
        return [('id', 'in', query)]

    @classmethod
    def _order_balance(cls, tables, date=None):
        table, _ = tables[None]
        balance_order = tables.get('balance_order')

        if balance_order is None:
            pool = Pool()
            MoveLine = pool.get('account.move.line')
            Account = pool.get('account.account')
            User = pool.get('res.user')

            line = MoveLine.__table__()
            account = Account.__table__()

            user = User(Transaction().user)
            if not user.company:
                return []
            company_id = user.company.id

            date_clause = Literal(True)
            if date:
                date_clause = ((line.maturity_date <= date)
                    | (line.maturity_date == Null))
            line_query, _ = MoveLine.query_get(line)

            balance = (Sum(Coalesce(line.debit, 0)) -
                Sum(Coalesce(line.credit, 0))).as_('balance')
            balance_table = line.join(account,
                condition=(account.id == line.account)
                ).select(line.contract, balance,
                where=(account.active
                    & (account.kind == 'receivable')
                    & (line.reconciliation == Null)
                    & (account.company == company_id)
                    & line_query
                    & date_clause),
                group_by=line.contract)

            balance_tables = {
                None: (balance_table,
                    balance_table.contract == table.id),
                }
            tables['balance_order'] = balance_tables

        return [Coalesce(balance_table.balance, 0)]

    @classmethod
    def order_balance(cls, tables):
        return cls._order_balance(tables)

    @classmethod
    def get_balance_today(cls, contracts, name):
        return cls.get_balance(contracts, name, date=utils.today())

    @classmethod
    def search_balance_today(cls, name, clause):
        return cls.search_balance(name, clause, date=utils.today())

    @classmethod
    def order_balance_today(cls, tables):
        return cls._order_balance(tables, date=utils.today())

    def get_balance_at_date(self, at_date):
        return self.get_balance([self], 'balance', date=at_date)[self.id]

    def get_valid_billing_informations(self, name):
        # apply domain only on current and future version
        # in order to manage subscriber change
        if not self.start_date:
            # Void contracts may be fully invalid
            return []
        res = []
        previous_date = datetime.date.max
        today = utils.today()
        for billing_info in reversed(self.billing_informations):
            # If the contract start_date is in the future, we must not validate
            # anything before it
            if previous_date > max(today, self.start_date):
                res.append(billing_info.id)
            previous_date = billing_info.date
        return res

    def invoices_report(self):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        non_periodic_invoices = ContractInvoice.search([
                ('contract', '=', self),
                ('invoice.state', 'not in', ('cancel', 'paid')),
                ('non_periodic', '=', True)])
        all_good_invoices = list(set(self.current_term_invoices) |
            set(non_periodic_invoices))
        amount_per_date = defaultdict(lambda: 0)
        for invoice in all_good_invoices:
            if invoice.invoice.lines_to_pay:
                for line in invoice.invoice.lines_to_pay:
                    amount_per_date[line.payment_date or line.date] +=\
                        line.amount
            else:
                amount_per_date[invoice.planned_payment_date] += \
                    invoice.invoice.total_amount
        invoices = [{
                'total_amount': amount_per_date[key],
                'planned_payment_date': key}
            for key in reversed(sorted(amount_per_date.keys()))]
        return [invoices[::-1],
            sum([x['total_amount'] for x in invoices])]

    def invoice_to_end_date(self):
        Contract.invoice([self], self.end_date)

    def get_non_periodic_payment_date(self):
        return self.product.get_non_periodic_payment_date(self)

    @dualmethod
    def invoice_non_periodic_premiums(cls, contracts, frequency):
        if not contracts:
            return []
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        AccountInvoice = pool.get('account.invoice')
        MoveLine = pool.get('account.move.line')
        Journal = pool.get('account.journal')
        journal, = Journal.search([
                ('type', '=', 'revenue'),
                ], limit=1)

        invoices_to_save = []
        payment_dates = []

        for contract in contracts:
            premiums = [p for p in contract.all_premiums if
                p.frequency == frequency]
            if not premiums:
                continue
            payment_date = contract.get_non_periodic_payment_date()
            __, __, billing_info = \
                contract._get_invoice_rrule_and_billing_information(
                    payment_date)
            new_invoice = contract.get_invoice(None, None, billing_info)
            new_invoice.journal = journal
            new_invoice.invoice_date = utils.today()
            if not new_invoice.invoice_address:
                new_invoice.invoice_address = contract.get_contract_address(
                    new_invoice.invoice_date)
            lines = []
            for premium in premiums:
                lines.extend(premium.get_invoice_lines(None, None))
            contract.finalize_invoices_lines(lines)
            new_invoice.lines = lines
            contract_invoice = ContractInvoice(non_periodic=True,
                invoice=new_invoice, contract=contract)
            invoices_to_save.append(contract_invoice)
            payment_dates.append({'payment_date': payment_date})

        AccountInvoice.save([x.invoice for x in invoices_to_save])
        ContractInvoice.save(invoices_to_save)
        AccountInvoice.post([x.invoice for x in invoices_to_save])
        lines_to_write = []
        for i, p in zip([x.invoice for x in invoices_to_save], payment_dates):
            lines_to_write += [list(i.lines_to_pay), p]
        if lines_to_write:
            MoveLine.write(*lines_to_write)
        return invoices_to_save

    def check_billing_information(self):
        for billing in self.billing_informations:
            if billing.direct_debit and not billing.direct_debit_account:
                parent = coop_string.translate_label(
                    self, 'billing_information')
                field = coop_string.translate_label(billing,
                    'direct_debit_account')
                self.append_functional_error('child_field_required',
                    (field, parent))

    @classmethod
    def get_billing_information(cls, contracts, names):
        pool = Pool()
        ContractBillingInformation = pool.get('contract.billing_information')
        return cls.get_revision_value(contracts, names,
            ContractBillingInformation)

    @classmethod
    def get_last_invoice(cls, contracts, name):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        Invoice = pool.get('account.invoice')
        cursor = Transaction().cursor
        table = cls.__table__()
        contract_invoice = ContractInvoice.__table__()
        invoice = Invoice.__table__()
        values = dict.fromkeys((c.id for c in contracts))
        in_max = cursor.IN_MAX
        state_column = Column(invoice, 'state')

        if name == 'last_invoice_start':
            column = 'start'
            where_clause = (state_column != 'cancel')
        elif name == 'last_invoice_end':
            column = 'end'
            where_clause = (state_column != 'cancel')
        elif name == 'last_posted_invoice_end':
            column = 'end'
            where_clause = (state_column == 'posted') | \
                (state_column == 'paid')
        elif name == 'last_paid_invoice_end':
            column = 'end'
            where_clause = (state_column == 'paid')
        else:
            raise NotImplementedError

        for i in range(0, len(contracts), in_max):
            sub_ids = [c.id for c in contracts[i:i + in_max]]
            where_id = reduce_ids(table.id, sub_ids)
            cursor.execute(*table.join(contract_invoice, 'LEFT',
                    table.id == contract_invoice.contract
                    ).join(invoice, 'LEFT',
                    invoice.id == contract_invoice.invoice
                    ).select(table.id, Max(getattr(contract_invoice, column)),
                    where=where_id & where_clause,
                    group_by=table.id))
            values.update(dict(cursor.fetchall()))
        return values

    def get_due_invoices(self, name):
        ContractInvoice = Pool().get('contract.invoice')
        invoices = ContractInvoice.search([
                ('contract', '=', self),
                ('invoice.state', '=', 'posted'),
                ])
        return [x.id for x in invoices if x.invoice.amount_to_pay_today > 0]

    def get_receivable_today(self, name):
        return sum([x.invoice.amount_to_pay_today for x in self.due_invoices])

    @classmethod
    def search_last_invoice(cls, name, domain):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        Invoice = pool.get('account.invoice')
        table = cls.__table__()
        contract_invoice = ContractInvoice.__table__()
        invoice = Invoice.__table__()

        column = name[len('last_invoice_'):]
        _, operator, value = domain
        Operator = fields.SQL_OPERATORS[operator]
        query = table.join(contract_invoice, 'LEFT',
            table.id == contract_invoice.contract
            ).join(invoice, 'LEFT',
                invoice.id == contract_invoice.contract
                ).select(table.id,
                    where=invoice.state != 'cancel',
                    group_by=table.id,
                    having=Operator(Max(getattr(contract_invoice, column)),
                        value))
        return [('id', 'in', query)]

    def clean_up_versions(self):
        BillingInformation = Pool().get('contract.billing_information')
        if self.billing_informations:
            billing_informations_to_del = [x
                for x in self.billing_informations[:-1]]
            self.billing_informations = [self.billing_informations[-1]]
            self.billing_informations[0].date = None
            if billing_informations_to_del:
                BillingInformation.delete(billing_informations_to_del)

    def _get_invoice_rrule_and_billing_information(self, start):
        billing_informations = iter(self.billing_informations)
        billing_information = billing_informations.next()
        for next_billing_information in billing_informations:
            if (next_billing_information.date or datetime.date.min) > start:
                break
            else:
                billing_information = next_billing_information
        else:
            next_billing_information = None
        until = None
        if next_billing_information:
            until = next_billing_information.date
        invoice_rrule = rruleset()
        rule, until_date = billing_information.billing_mode.get_rrule(start,
            until)
        invoice_rrule.rrule(rule)
        return (invoice_rrule, until_date, billing_information)

    def get_invoice_periods(self, up_to_date, from_date=None):
        if from_date:
            start = max(from_date, self.start_date)
        elif self.last_invoice_end:
            start = self.last_invoice_end + relativedelta(days=+1)
        else:
            start = self.start_date
        if up_to_date and start > up_to_date:
            return []
        periods = []
        while (up_to_date and start < up_to_date) or len(periods) < 1:
            rule, until, billing_information =\
                self._get_invoice_rrule_and_billing_information(start)
            for date in rule:
                if hasattr(date, 'date'):
                    date = date.date()
                if date <= start:
                    continue
                end = date + relativedelta(days=-1)
                periods.append((start, min(end, self.end_date or
                            datetime.date.max), billing_information))
                start = date
                if (up_to_date and start >= up_to_date) or not up_to_date:
                    break
            if until and (up_to_date and until < up_to_date):
                if self.end_date and self.end_date < up_to_date:
                    if until > self.end_date:
                        until = self.end_date
                if start != until:
                    end = until + relativedelta(days=-1)
                    periods.append((start, end, billing_information))
                    start = until
        return periods

    @classmethod
    def clean_up_contract_invoices(cls, contracts, from_date=None,
            to_date=None):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        contract_invoices = []
        for contract_slice in grouped_slice(contracts):
            contract_invoices += ContractInvoice.search([
                    ('contract', 'in', [x.id for x in contract_slice]),
                    ['OR',
                        ('contract.status', '=', 'void'),
                        ('start', '<=', to_date or datetime.date.min),
                        ('end', '>=', from_date or datetime.date.max)],
                    ])

        actions = {
            'cancel': [],
            'delete': [],
            }
        for contract_invoice in contract_invoices:
            actions[contract_invoice.cancel_or_delete()].append(
                contract_invoice)
        if actions['delete']:
            ContractInvoice.delete(actions['delete'])
        if actions['cancel']:
            ContractInvoice.cancel(actions['cancel'])

    @classmethod
    def _first_invoice(cls, contracts, and_post=False):
        with Transaction().set_user(0, set_context=True):
            Invoice = Pool().get('account.invoice')
            # Make sure all existing invoices are cleaned up
            cls.clean_up_contract_invoices(contracts,
                from_date=datetime.date.min)
            contract_invoices = []
            for contract in contracts:
                invoices = cls.invoice([contract], max(contract.start_date,
                        utils.today()))
                for invoice in invoices:
                    # We need to update the function field as the
                    # contract has not been stored since it has been activated
                    invoice.invoice.contract = contract
                contract_invoices += invoices
            if not and_post:
                return
            Invoice.post([x.invoice for x in contract_invoices])

    @classmethod
    def first_invoice(cls, contracts):
        cls._first_invoice(contracts, and_post=False)

    @classmethod
    def first_invoice_and_post(cls, contracts):
        cls._first_invoice(contracts, and_post=True)

    @classmethod
    def invoice(cls, contracts, up_to_date):
        'Invoice contracts up to the date'
        periods = defaultdict(list)
        for contract in contracts:
            if contract.status not in ('active', 'quote', 'terminated'):
                continue
            cls._invoices_cache.set(contract.id, None)
            for period in contract.get_invoice_periods(min(up_to_date,
                        contract.end_date or datetime.date.max)):
                periods[period].append(contract)

        return cls.invoice_periods(periods)

    @classmethod
    def invoice_periods(cls, periods):
        'Invoice periods for contracts'
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ContractInvoice = pool.get('contract.invoice')
        Journal = pool.get('account.journal')
        journals = Journal.search([
                ('type', '=', 'revenue'),
                ], limit=1)
        if journals:
            journal, = journals
        else:
            journal = None

        invoices = defaultdict(list)
        for period in sorted(periods.iterkeys(), key=lambda x: x[0]):
            for contract in periods[period]:
                invoice = contract.get_invoice(*period)
                if not invoice.journal:
                    invoice.journal = journal
                if not invoice.invoice_address:
                    invoice.invoice_address = contract.get_contract_address(
                        period[0])
                invoice.lines = contract.get_invoice_lines(*period[0:2])
                invoices[period].append((contract, invoice))
        new_invoices = Invoice.create([i._save_values
                 for contract_invoices in invoices.itervalues()
                 for c, i in contract_invoices])

        # Set the new ids
        old_invoices = (i for ci in invoices.itervalues() for c, i in ci)
        for invoice, new_invoice in zip(old_invoices, new_invoices):
            invoice.id = new_invoice.id
        contract_invoices_to_create = []
        for period, contract_invoices in invoices.iteritems():
            start, end, billing_information = period
            for contract, invoice in contract_invoices:
                contract_invoices_to_create.append(ContractInvoice(
                        contract=contract,
                        invoice=invoice,
                        start=start,
                        end=end))
        contracts_invoices = ContractInvoice.create([c._save_values
                for c in contract_invoices_to_create])

        # Update taxes once contract_invoice are created
        Invoice.update_taxes(new_invoices)
        return contracts_invoices

    def get_invoice(self, start, end, billing_information):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        lang = self.company.party.lang
        return Invoice(
            company=self.company,
            type='out_invoice',
            journal=None,
            party=self.subscriber,
            invoice_address=self.get_contract_address(
                max(start or datetime.date.min, utils.today())),
            currency=self.get_currency(),
            account=self.subscriber.account_receivable,
            payment_term=billing_information.payment_term,
            state='validated',
            description='%s (%s - %s)' % (
                self.rec_name,
                lang.strftime(start, lang.code, lang.date) if start else '',
                lang.strftime(end, lang.code, lang.date) if end else '',
            ))

    def finalize_invoices_lines(self, lines):
        for line in lines:
            line.company = self.company

    def get_invoice_lines(self, start, end):
        lines = self.compute_invoice_lines(start, end)
        self.finalize_invoices_lines(lines)
        return lines

    def compute_invoice_lines(self, start, end):
        lines = []
        for premium in self.all_premiums:
            if end < (premium.start or datetime.date.min):
                break
            lines.extend(premium.get_invoice_lines(start, end))
        return lines

    def get_rebill_end_date(self):
        return self.end_date

    def get_rebill_post_end(self, rebill_end):
        ContractInvoice = Pool().get('contract.invoice')
        last_posted = ContractInvoice.search([
                ('contract', '=', self.id),
                ('end', '>=', rebill_end),
                ('invoice_state', 'not in', ('cancel', 'draft', 'validated')),
                ], order=[('start', 'DESC')], limit=1)
        return last_posted[0].start if last_posted else utils.today()

    def rebill(self, start, end=None, post_end=None):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        # Store the end date of the last invoice to be able to know up til when
        # we should rebill
        rebill_end = end or self.get_rebill_end_date() or utils.today()

        # Calculate the date until which we will repost invoices
        post_end = post_end or self.get_rebill_post_end(
            rebill_end) or utils.today()

        # Delete or cancel overlapping invoices
        self.clean_up_contract_invoices([self], from_date=start)

        # Rebill
        if not rebill_end:
            return
        self.invoice([self], rebill_end)

        # Post
        if not post_end:
            return
        invoices_to_post = Invoice.search([
                ('contract', '=', self.id),
                ('start', '<=', post_end),
                ('state', '=', 'validated')], order=[('start', 'ASC')])
        if invoices_to_post:
            Invoice.post(invoices_to_post)

    @classmethod
    def get_lines_to_reconcile(cls, contracts):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        # Find all not reconciled lines
        subscribers = defaultdict(list)
        for contract in contracts:
            subscribers[contract.subscriber].append(contract)
        clause = [
            ('reconciliation', '=', None),
            ('date', '<=', utils.today()),
            ('move_state', 'not in', ('draft', 'validated'))]
        subscriber_clause = ['OR']
        for subscriber, contract_group in subscribers.iteritems():
            subscriber_clause.append([
                    ('party', '=', subscriber.id),
                    ('account', '=', subscriber.account_receivable.id),
                    ('contract', 'in', [x.id for x in contract_group]),
                    ])
        clause.append(subscriber_clause)
        may_be_reconciled = MoveLine.search(clause,
            order=[('contract', 'ASC'), ('date', 'ASC')])

        per_contract = defaultdict(list)
        for line in may_be_reconciled:
            per_contract[line.contract].append(line)

        reconciliations = {}

        for contract, possible_lines in per_contract.iteritems():
            # Split lines in available amount / amount to pay
            available, to_pay, total_available = [], [], Decimal(0)
            for line in possible_lines:
                if line.credit > 0 or line.debit < 0:
                    available.append(line)
                    total_available += line.credit - line.debit
                else:
                    to_pay.append(line)
            if not to_pay or not available:
                continue

            # Do reconciliation. Lines are ordered by date
            to_reconcile, total_to_reconcile = [], Decimal(0)
            for line in to_pay:
                if line.debit - line.credit > total_available:
                    break
                to_reconcile.append(line)
                total_available -= line.debit - line.credit
                total_to_reconcile += line.debit - line.credit
            if not to_reconcile:
                continue

            # Select lines for payment in date order
            for line in available:
                if total_to_reconcile <= 0:
                    break
                total_to_reconcile -= line.credit - line.debit
                to_reconcile.append(line)

            reconciliations[contract] = (to_reconcile, max(0,
                    -total_to_reconcile))

        # Split lines if necessary
        splits = MoveLine.split_lines([(lines[-1], split_amount)
                for _, (lines, split_amount) in reconciliations.iteritems()
                if split_amount != 0])

        reconciliation_lines = []
        for contract, (lines, split_amount) in reconciliations.iteritems():
            reconciliation_lines.append(lines)
            if split_amount == 0:
                continue

            # If a line was split, add the matching line to the reconciliation
            _, remaining, compensation = splits[lines[-1]]
            lines += [remaining, compensation]

        return reconciliation_lines

    @dualmethod
    def reconcile(cls, contracts):
        pool = Pool()
        Reconciliation = pool.get('account.move.reconciliation')
        lines_to_reconcile, reconciliations = [], []
        lines_to_reconcile = cls.get_lines_to_reconcile(contracts)
        for reconciliation_lines in lines_to_reconcile:
            if not reconciliation_lines:
                continue
            reconciliations.append(Reconciliation(lines=reconciliation_lines))
        if reconciliations:
            Reconciliation.save(reconciliations)
        return reconciliations

    def init_from_product(self, product, start_date=None, end_date=None):
        pool = Pool()
        super(Contract, self).init_from_product(product, start_date, end_date)
        BillingInformation = pool.get('contract.billing_information')
        if not product.billing_modes:
            return
        default_billing_mode = product.billing_modes[0]
        if default_billing_mode.direct_debit:
            days = default_billing_mode.get_allowed_direct_debit_days()
            direct_debit_day = days[0][0]
        else:
            direct_debit_day = 0
        self.billing_informations = [BillingInformation(start=self.start_date,
            billing_mode=default_billing_mode,
            payment_term=default_billing_mode.allowed_payment_terms[0],
            direct_debit_day=direct_debit_day)]

    @classmethod
    def update_contract_after_import(cls, contracts):
        super(Contract, cls).update_contract_after_import(contracts)
        for contract in contracts:
            for billing_information in contract.billing_informations:
                if (not billing_information.payment_term):
                    billing_information.payment_term = billing_information.\
                        billing_mode.allowed_payment_terms[0]
                    billing_information.save()

    @classmethod
    def ws_rate_contracts(cls, contract_dict):
        '''
            This methods uses the ws_subscribe_contracts methods to create a
            contract, rate it, extract data to return, then rollback
            everything.
        '''
        with Transaction().new_cursor():
            try:
                messages = cls.ws_subscribe_contracts(contract_dict)
                if len(messages) == 1 and not messages.values()[0]['return']:
                    # ws_subscribe_contracts failed, forward the message
                    return messages
                quote_numbers = [message['quote_number']
                    for root_message in messages.itervalues()
                    for message in root_message['messages']
                    if root_message['return'] and 'quote_number' in message]
                new_contracts = cls.search([
                        ('quote_number', 'in', quote_numbers)])
                rating_message = {
                    'return': True,
                    'messages': cls._ws_extract_rating_message(new_contracts),
                    }
            except UserError as exc:
                rating_message = {
                    'return': False,
                    'messages': [{'error': str(exc)}],
                    }
            finally:
                Transaction().cursor.rollback()
            return {contract_dict.keys()[0]: rating_message}

    @classmethod
    def _ws_extract_rating_message(cls, contracts):
        # TODO : Complete with the actual ratings
        return {contract.quote_number: {'name': contract.rec_name}
            for contract in contracts}

    @classmethod
    def terminate(cls, contracts, at_date, termination_reason):
        super(Contract, cls).terminate(contracts, at_date, termination_reason)
        cls.calculate_prices(contracts, at_date)
        for contract in contracts:
            contract.rebill(at_date)
        cls.reconcile(contracts)

    @classmethod
    def reactivate(cls, contracts):
        previous_dates = {x.id: x.end_date for x in contracts}
        super(Contract, cls).reactivate(contracts)
        for contract in contracts:
            cls.calculate_prices([contract], previous_dates[contract.id])
            contract.rebill(previous_dates[contract.id])
        cls.reconcile(contracts)

    @classmethod
    def void(cls, contracts, void_reason):
        super(Contract, cls).void(contracts, void_reason)
        cls.calculate_prices(contracts, datetime.date.min)
        for contract in contracts:
            contract.rebill(datetime.date.min)
        cls.reconcile(contracts)


class ContractFee:
    __name__ = 'contract.fee'

    active = fields.Boolean('Active')

    @classmethod
    def default_active(cls):
        return True

    @classmethod
    def delete(cls, contract_fees):
        to_deactivate = []
        contract_fee_dict = {x.id: x for x in contract_fees}

        cursor = Transaction().cursor
        invoice_detail = Pool().get('account.invoice.line.detail').__table__()
        for contract_fee_slice in grouped_slice(contract_fees):
            cursor.execute(*invoice_detail.select(invoice_detail.contract_fee,
                    Count(invoice_detail.id), where=(
                        invoice_detail.contract_fee.in_(
                            [x.id for x in contract_fee_slice])),
                    group_by=invoice_detail.contract_fee))
            for contract_fee_id, _ in cursor.fetchall():
                to_deactivate.append(contract_fee_dict.pop(contract_fee_id))
        if to_deactivate:
            cls.write(to_deactivate, {'active': False})
        if contract_fee_dict:
            super(ContractFee, cls).delete(contract_fee_dict.values())


class ContractOption:
    __name__ = 'contract.option'

    @classmethod
    def delete(cls, options):
        to_decline = []
        option_dict = {x.id: x for x in options}

        cursor = Transaction().cursor
        invoice_detail = Pool().get('account.invoice.line.detail').__table__()
        for option_slice in grouped_slice(options):
            cursor.execute(*invoice_detail.select(invoice_detail.option,
                    Count(invoice_detail.id), where=(
                        invoice_detail.option.in_(
                            [x.id for x in option_slice])),
                    group_by=invoice_detail.option))
            for option_id, _ in cursor.fetchall():
                to_decline.append(option_dict.pop(option_id))
        if to_decline:
            cls.write(to_decline, {'status': 'declined'})
        if option_dict:
            super(ContractOption, cls).delete(option_dict.values())


class ExtraPremium:
    __name__ = 'contract.option.extra_premium'

    active = fields.Boolean('Active')

    @classmethod
    def default_active(cls):
        return True

    @classmethod
    def delete(cls, extra_premiums):
        to_deactivate = []
        extra_premium_dict = {x.id: x for x in extra_premiums}

        cursor = Transaction().cursor
        invoice_detail = Pool().get('account.invoice.line.detail').__table__()
        for extra_premium_slice in grouped_slice(extra_premiums):
            cursor.execute(*invoice_detail.select(invoice_detail.extra_premium,
                    Count(invoice_detail.id), where=(
                        invoice_detail.extra_premium.in_(
                            [x.id for x in extra_premium_slice])),
                    group_by=invoice_detail.extra_premium))
            for extra_premium_id, _ in cursor.fetchall():
                to_deactivate.append(extra_premium_dict.pop(extra_premium_id))
        if to_deactivate:
            cls.write(to_deactivate, {'active': False})
        if extra_premium_dict:
            super(ExtraPremium, cls).delete(extra_premium_dict.values())


class ContractBillingInformation(model._RevisionMixin, model.CoopSQL,
        model.CoopView):
    'Contract Billing Information'
    __name__ = 'contract.billing_information'
    _parent_name = 'contract'
    _func_key = 'date'

    contract = fields.Many2One('contract', 'Contract', required=True,
        select=True, ondelete='CASCADE')
    billing_mode = fields.Many2One('offered.billing_mode', 'Billing Mode',
        required=True, ondelete='RESTRICT')
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', ondelete='RESTRICT', states={
            'required': And(Eval('direct_debit', False),
                (Eval('_parent_contract', {}).get('status', '') == 'active')),
            'invisible': Len(Eval('possible_payment_terms', [])) < 2},
        domain=[('id', 'in', Eval('possible_payment_terms'))],
        depends=['possible_payment_terms'])
    direct_debit = fields.Function(
        fields.Boolean('Direct Debit Payment'), 'on_change_with_direct_debit',
        searcher='search_direct_debit')
    direct_debit_day_selector = fields.Function(
        fields.Selection('get_allowed_direct_debit_days',
            'Direct Debit Day', states={
                'invisible': ~Eval('direct_debit', False),
                'required': And(Eval('direct_debit', False),
                    (Eval('_parent_contract', {}).get('status', '') ==
                        'active'))},
            sort=False, depends=['direct_debit']),
        'get_direct_debit_day_selector', 'set_direct_debit_day_selector')
    direct_debit_day = fields.Integer('Direct Debit Day')
    direct_debit_account = fields.Many2One('bank.account',
        'Direct Debit Account',
        states={'invisible': ~Eval('direct_debit')},
        depends=['direct_debit'], ondelete='RESTRICT')
    possible_payment_terms = fields.Function(fields.One2Many(
            'account.invoice.payment_term', None, 'Possible Payment Term'),
            'on_change_with_possible_payment_terms')
    is_once_per_contract = fields.Function(
        fields.Boolean('Once Per Contract?'),
        'on_change_with_is_once_per_contract')

    @classmethod
    def _export_light(cls):
        return (super(ContractBillingInformation, cls)._export_light() |
            set(['payment_term', 'direct_debit_account', 'billing_mode']))

    @classmethod
    def __setup__(cls):
        super(ContractBillingInformation, cls).__setup__()
        cls.__rpc__.update({
                'get_allowed_direct_debit_days': RPC(instantiate=0)
                })

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.1: Billing change
        migrate = False
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        if (not TableHandler.table_exist(cursor,
                'contract_billing_information') and TableHandler.table_exist(
                    cursor, 'contract_invoice_frequency')):
            migrate = True

        super(ContractBillingInformation, cls).__register__(module_name)

        # Migration from 1.1: Billing change
        if migrate:
            cursor.execute('insert into '
                '"contract_billing_information" '
                '(id, create_uid, create_date, write_uid, write_date,'
                'billing_mode, contract, date, direct_debit_day, '
                'direct_debit_account) '
                'select f.id, f.create_uid, f.create_date, f.write_uid, '
                'f.write_date, f.value, f.contract, f.date, '
                'cast(c.direct_debit_day as integer), '
                'c.direct_debit_account from '
                'contract_invoice_frequency as f, '
                'contract as c where f.contract = c.id')

    @staticmethod
    def revision_columns():
        return ['billing_mode', 'payment_term', 'direct_debit_day',
            'direct_debit_account']

    @classmethod
    def get_reverse_field_name(cls):
        return 'billing_information'

    @fields.depends('billing_mode')
    def get_allowed_direct_debit_days(self):
        if not self.billing_mode:
            return [('', '')]
        return self.billing_mode.get_allowed_direct_debit_days()

    def get_direct_debit_day_selector(self, name):
        if not self.direct_debit:
            return ''
        return str(self.direct_debit_day)

    @classmethod
    def set_direct_debit_day_selector(cls, ids, name, value):
        if not value:
            return
        cls.write(ids, {'direct_debit_day': int(value)})

    @fields.depends('billing_mode')
    def on_change_with_direct_debit(self, name=None):
        if self.billing_mode:
            return self.billing_mode.direct_debit

    @fields.depends('billing_mode')
    def on_change_with_possible_payment_terms(self, name=None):
        if not self.billing_mode:
            return []
        return [x.id for x in self.billing_mode.allowed_payment_terms]

    @fields.depends('billing_mode')
    def on_change_with_payment_term(self, name=None):
        if self.billing_mode:
            return self.billing_mode.allowed_payment_terms[0].id

    @fields.depends('direct_debit_day_selector')
    def on_change_direct_debit_day_selector(self):
        if not self.direct_debit_day_selector:
            self.direct_debit_day = None
            return
        self.direct_debit_day = int(self.direct_debit_day_selector)

    @fields.depends('billing_mode')
    def on_change_with_is_once_per_contract(self, name=None):
        return (self.billing_mode.frequency == 'once_per_contract'
            if self.billing_mode else False)

    def get_direct_debit_planned_date(self, line):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        if not (self.direct_debit and self.direct_debit_day):
            return None
        if type(line) == dict:
            curline = MoveLine(**line)
        else:
            curline = line
        payment_journal = curline.get_payment_journal()
        return payment_journal.get_next_possible_payment_date(line,
            self.direct_debit_day)

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values.get('date', None)

    @classmethod
    def search_direct_debit(cls, name, domain):
        return [('billing_mode.direct_debit',) + tuple(domain[1:])]


class Premium:
    __name__ = 'contract.premium'

    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('company', '=', Eval('context', {}).get('company', -1)),
            ['OR', [('kind', '=', 'revenue')], [('kind', '=', 'other')]]
            ],
        ondelete='RESTRICT')

    @classmethod
    def _export_light(cls):
        return super(Premium, cls)._export_light() | {'account'}

    def same_value(self, other):
        result = super(Premium, self).same_value(other)
        return result and self.account == other.account

    @classmethod
    def new_line(cls, line, start_date, end_date):
        new_line = super(Premium, cls).new_line(line, start_date, end_date)
        if not new_line:
            return None
        new_line.account = line.account
        return new_line

    def get_description(self):
        return getattr(self.parent, 'full_name', self.parent.rec_name)

    def _get_rrule(self, start):
        if self.frequency in ('monthly', 'quarterly', 'half_yearly'):
            freq = MONTHLY
            interval = {
                'monthly': 1,
                'quarterly': 3,
                'half_yearly': 6,
                }.get(self.frequency)
        elif self.frequency == 'yearly':
            freq = DAILY
            # Get current year contract start_date
            rule_start = datetime.datetime.combine(
                datetime.date(start.year - 1, start.month, start.day),
                datetime.time())
            rule = rrule(DAILY, bymonth=self.main_contract.start_date.month,
                bymonthday=self.main_contract.start_date.day,
                dtstart=rule_start)
            year_start = rule.before(datetime.datetime.combine(start,
                    datetime.time()), inc=True)
            interval = 366 if calendar.isleap(year_start.year) else 365
        elif self.frequency == 'yearly_360':
            freq = DAILY
            interval = 360
        elif self.frequency == 'yearly_365':
            freq = DAILY
            interval = 365
        elif self.frequency in ('once_per_contract'):
            return rrule(MONTHLY, dtstart=self.start, count=2)
        else:
            return
        return rrule(freq, interval=interval, dtstart=start)

    def get_amount(self, start, end):
        if self.frequency == 'once_per_invoice':
            return self.amount
        if start is None:
            return self.amount if self.frequency == 'at_contract_signature' \
                else 0
        elif self.frequency == 'at_contract_signature':
            return 0
        elif self.frequency == 'once_per_year':
            start_date = self.main_contract.start_date
            stick = (start_date.month, start_date.day) == (2, 29)
            amount = 0
            for year in xrange(end.year - start.year + 1):
                new_date = coop_date.add_year(start_date, start.year -
                        start_date.year + year, stick)
                if start <= new_date <= end:
                    amount += self.amount
            return amount
        # For yearly frequencies, only use the date to calculate the prorata on
        # the remaining days, after taking the full years out.
        #
        # This is necessary since the yearly frequency is translated in a
        # daily rule because the number of days may vary.
        occurences = []
        if self.frequency.startswith('yearly'):
            nb_years = coop_date.number_of_years_between(start, end)
            if nb_years:
                occurences = [None] * (nb_years - 1) + [
                    coop_date.add_year(start, nb_years)]
                start = occurences[-1]
                occurences[-1] = datetime.datetime.combine(occurences[-1],
                    datetime.time())
        rrule = self._get_rrule(start)
        start = datetime.datetime.combine(start, datetime.time())
        end = datetime.datetime.combine(end, datetime.time())
        if not occurences:
            occurences = rrule.between(start, end + datetime.timedelta(2))
        amount = len(occurences) * self.amount
        try:
            last_date = occurences[-1]
        except IndexError:
            last_date = start
        next_date = rrule.after(last_date)
        if self.frequency in ('once_per_contract'):
            if (last_date <= datetime.datetime.combine(self.start,
                    datetime.time()) <= next_date):
                return self.amount
            elif (start <= datetime.datetime.combine(self.start,
                    datetime.time())):
                return self.amount
            else:
                return 0
        if next_date and (next_date - end).days > 1:
            if (next_date - last_date).days != 0:
                ratio = (Decimal((end - last_date).days + 1)
                    / Decimal((next_date - last_date).days))
                amount += self.amount * ratio
        return amount

    def get_invoice_lines(self, start, end):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        InvoiceLineDetail = pool.get('account.invoice.line.detail')
        Tax = pool.get('account.tax')
        if start is not None and end is not None:
            if ((self.start or datetime.date.min) > end
                    or (self.end or datetime.date.max) < start):
                return []
            start = (start if start > (self.start or datetime.date.min)
                else self.start)
            end = end if end < (self.end or datetime.date.max) else self.end
        line_amount = self.get_amount(start, end)
        if not line_amount:
            return []
        if self.main_contract.product.taxes_included_in_premium:
            line_amount = Tax.reverse_compute(line_amount, self.taxes, start)
            line_amount = line_amount.quantize(
                Decimal(1) / 10 ** InvoiceLine.unit_price.digits[1])
        else:
            line_amount = self.main_contract.company.currency.round(
                line_amount)
        return [InvoiceLine(
                type='line',
                description=self.get_description(),
                origin=self.main_contract,
                quantity=1,
                unit=None,
                unit_price=line_amount,
                taxes=self.taxes,
                invoice_type='out_invoice',
                account=self.account,
                coverage_start=start,
                coverage_end=end,
                details=[InvoiceLineDetail.new_detail_from_premium(self)],
                )]


class ContractInvoice(model.CoopSQL, model.CoopView):
    'Contract Invoice'
    __name__ = 'contract.invoice'
    _rec_name = 'invoice'

    contract = fields.Many2One('contract', 'Contract', required=True,
        ondelete='CASCADE', select=True)
    invoice = fields.Many2One('account.invoice', 'Invoice', required=True,
        ondelete='CASCADE', select=True)
    invoice_state = fields.Function(
        fields.Char('Invoice State'),
        'get_invoice_state', searcher='search_invoice_state')
    start = fields.Date('Start Date', depends=['non_periodic'], states={
            'required': ~Eval('non_periodic')})
    end = fields.Date('End Date', depends=['non_periodic'], states={
            'required': ~Eval('non_periodic')})
    planned_payment_date = fields.Function(fields.Date('Planned Payment Date'),
        'get_planned_payment_date')
    non_periodic = fields.Boolean('Non Periodic')

    @classmethod
    def __setup__(cls):
        super(ContractInvoice, cls).__setup__()
        cls._order.insert(0, ('start', 'DESC'))
        cls._buttons.update({
                'reinvoice': {
                    'invisible': Eval('invoice_state') == 'cancel',
                    },
                'cancel': {
                    'invisible': Eval('invoice_state') == 'cancel',
                    },
                })

    @classmethod
    def default_non_periodic(cls):
        return False

    def get_invoice_state(self, name):
        return self.invoice.state

    def get_planned_payment_date(self, name):
        if self.invoice_state in ['posted', 'paid']:
            date = self.invoice.lines_to_pay[0].payment_date
            assert all([(x.payment_date == date for x in
                    self.invoice.lines_to_pay)])
            return date
        with Transaction().set_context({'contract_revision_date':
                    self.invoice.start}):
            billing_info = self.contract.billing_information
            return billing_info.get_direct_debit_planned_date({
                    'maturity_date': self.invoice.start or datetime.date.min,
                    'contract': self.contract})

    @classmethod
    def search_invoice_state(cls, name, domain):
        return [('invoice.state',) + tuple(domain[1:])]

    @classmethod
    def validate(cls, contract_invoices):
        super(ContractInvoice, cls).validate(contract_invoices)
        for contract_invoice in contract_invoices:
            contract_invoice.check_dates()

    def check_dates(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        cursor = Transaction().cursor
        table = self.__table__()
        invoice = Invoice.__table__()
        cursor.execute(*table.join(invoice,
                condition=table.invoice == invoice.id
                ).select(table.id,
                where=(((table.start <= self.start)
                        & (table.end >= self.start))
                    | ((table.start <= self.end)
                        & (table.end >= self.end))
                    | ((table.start >= self.start)
                        & (table.end <= self.end)))
                    & (table.contract == self.id)
                    & (invoice.state != 'cancel')))

    @classmethod
    @model.CoopView.button
    def reinvoice(cls, contract_invoices):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Contract = pool.get('contract')
        invoices = []
        for contract_invoice in contract_invoices:
            assert contract_invoice.invoice_state != 'cancel'
            invoices.append(contract_invoice.invoice)
        Invoice.cancel(invoices)
        periods = defaultdict(list)
        for contract_invoice in contract_invoices:
            period = contract_invoice.start, contract_invoice.end
            periods[period].append(contract_invoice.contract)
        Contract.invoice_periods(periods)

    @classmethod
    @model.CoopView.button
    def cancel(cls, contract_invoices):
        pool = Pool()
        Reconciliation = pool.get('account.move.reconciliation')
        Invoice = pool.get('account.invoice')

        invoices = [c.invoice for c in contract_invoices]
        reconciliations = []
        for invoice in invoices:
            if invoice.move:
                for line in invoice.move.lines:
                    if line.reconciliation:
                        reconciliations.append(line.reconciliation)
        if reconciliations:
            Reconciliation.delete(reconciliations)
        Invoice.cancel(invoices)

    @classmethod
    def delete(cls, contract_invoices):
        Invoice = Pool().get('account.invoice')
        Invoice.delete([x.invoice for x in contract_invoices])
        super(ContractInvoice, cls).delete(contract_invoices)

    def cancel_or_delete(self):
        if self.invoice_state in ('validated', 'draft'):
            return 'delete'
        return 'cancel'


class InvoiceContractStart(model.CoopView):
    'Invoice Contract'
    __name__ = 'contract.do_invoice.start'
    up_to_date = fields.Date('Up To Date', required=True)


class InvoiceContract(Wizard):
    'Invoice Contract'
    __name__ = 'contract.do_invoice'
    start = StateView('contract.do_invoice.start',
        'contract_insurance_invoice.invoice_start_view_form', [
            Button('Cancel', 'end', icon='tryton-cancel'),
            Button('Ok', 'invoice', icon='tryton-ok', default=True),
            ])
    invoice = StateTransition()

    def default_start(self, name):
        if Transaction().context.get('active_model', '') != 'contract':
            return {}
        if len(Transaction().context.get('active_ids', [])) != 1:
            return {}
        pool = Pool()
        Contract = pool.get('contract')
        contract = Contract(Transaction().context.get('active_ids')[0])
        if contract.last_invoice_end:
            return {
                'up_to_date': coop_date.add_day(contract.last_invoice_end, 1),
                }
        else:
            return {
                'up_to_date': contract.start_date,
                }

    def transition_invoice(self):
        pool = Pool()
        Contract = pool.get('contract')
        contracts = Contract.browse(Transaction().context['active_ids'])
        Contract.invoice(contracts, self.start.up_to_date)
        return 'end'


class DisplayContractPremium:
    __name__ = 'contract.premium.display'

    @classmethod
    def get_children_fields(cls):
        children = super(DisplayContractPremium, cls).get_children_fields()
        children['contract'].append('covered_elements')
        children['contract.covered_element'] = ['options']
        children['options'].append('extra_premiums')
        return children
