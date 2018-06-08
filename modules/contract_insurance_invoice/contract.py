# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import intervaltree
import datetime
from collections import defaultdict
from decimal import Decimal
from itertools import groupby

from sql import Column, Null, Literal
from sql.aggregate import Max, Count, Sum
from sql.conditionals import Coalesce

from dateutil.rrule import rruleset
from dateutil.relativedelta import relativedelta

from trytond.pool import Pool, PoolMeta
from trytond.model import dualmethod
from trytond.pyson import Eval, And, Len, If, Bool, Or, PYSONEncoder
from trytond.error import UserError
from trytond import backend
from trytond.transaction import Transaction
from trytond.tools import reduce_ids, grouped_slice
from trytond.wizard import Wizard, StateView, Button, StateAction
from trytond.rpc import RPC
from trytond.cache import Cache
from trytond.server_context import ServerContext

from trytond.modules.coog_core import (coog_date, coog_string, utils, model,
    fields)
from trytond.modules.coog_core.cache import CoogCache, get_cache_holder
from trytond.modules.contract import _STATES
from trytond.modules.contract import _CONTRACT_STATUS_STATES
from trytond.modules.contract import _CONTRACT_STATUS_DEPENDS

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
    'ContractSubStatus',
    ]

FREQUENCIES = [
    ('once_per_contract', 'Once Per Contract'),
    ('monthly', 'Monthly'),
    ('quarterly', 'Quarterly'),
    ('half_yearly', 'Half-yearly'),
    ('yearly', 'Yearly'),
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    block_invoicing_until = fields.Date('Block Invoicing Until', readonly=True,
        states={'invisible': ~Eval('block_invoicing_until')},
        help='If set, no invoices will be generated before this date, and the '
        'first invoice will start at this date')
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
            'Current Billing Information'),
        'get_billing_information', loader='load_billing_information')
    payer = fields.Function(
        fields.Many2One('party.party', 'Payer'),
        'get_billing_information')
    billing_informations = fields.One2Many('contract.billing_information',
        'contract', 'Billing Information',
        domain=[
            ('billing_mode.products', '=', Eval('product')),
            If(Bool(Eval('status') == 'active'),
                ['OR',
                    ('direct_debit', '=', False),
                    ('direct_debit_account', '!=', None)],
                [])
        ], delete_missing=True,
        states=_STATES, depends=['product', 'status', 'id'])
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
    processing_payments_amount = fields.Function(
        fields.Numeric('Processing Payments Amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_processing_payments_amount')
    total_premium_amount = fields.Function(
        fields.Numeric('Total Premium Amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_total_premium_amount')

    _invoices_cache = Cache('invoices_report')
    _future_invoices_cache = Cache('future_invoices', context=False)

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
                'rebill_contracts': {},
                })
        cls._error_messages.update({
                'no_payer': 'A payer must be specified',
                'missing_invoices': 'This contract can not be renewed because '
                'there are missing invoices on the current term '
                })

    def get_color_from_balance_today(self):
        if self.status in ['void', 'terminated'] and self.balance_today != 0:
            return 'red'

    def get_color(self, name):
        if self.billing_information and self.billing_information.suspended:
            return 'red'
        return (self.get_color_from_balance_today() or
            super(Contract, self).get_color(name))

    @classmethod
    def delete(cls, contracts):
        pool = Pool()
        Invoice = pool.get('contract.invoice')
        Invoice.delete(Invoice.search([('contract', 'in',
                        [x.id for x in contracts])]))
        super(Contract, cls).delete(contracts)

    @fields.depends('subscriber', 'billing_informations')
    def on_change_subscriber(self):
        if not self.billing_informations:
            return
        new_billing_information = self.billing_informations[-1]
        new_billing_information.date = None
        new_billing_information.payer = self.subscriber
        if new_billing_information.direct_debit_account:
            if (new_billing_information.payer not in
                    new_billing_information.direct_debit_account.owners):
                new_billing_information.direct_debit_account = None
        self.billing_informations = [new_billing_information]

    def appliable_fees(self):
        all_fees = super(Contract, self).appliable_fees()
        if self.billing_informations:
            if self.billing_informations[-1].billing_mode:
                all_fees |= set(
                    self.billing_informations[-1].billing_mode.fees)
        return all_fees

    def get_current_term_invoices(self, name):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        return [x.id for x in ContractInvoice.search([
                    ('contract', '=', self),
                    ('invoice.state', 'not in', ('cancel', 'paid')),
                    ('start', '>=', self.start_date),
                    ('end', '<=', self.end_date or datetime.date.max),
                    ])]

    def get_total_premium_amount(self, name):
        if (not self.subscriber or not self.billing_informations or
                not self.all_premiums):
            # Test on all_premiums at the end since it may be rather expensive
            return None
        return sum(x['total_amount'] for x in self.get_future_invoices(self))

    @classmethod
    def get_balance(cls, contracts, name, date=None):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Account = pool.get('account.account')
        User = pool.get('res.user')
        cursor = Transaction().connection.cursor()

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

    @classmethod
    def get_processing_payments_amount(cls, contracts, name):
        pool = Pool()
        payment = pool.get('account.payment').__table__()
        line = pool.get('account.move.line').__table__()
        cursor = Transaction().connection.cursor()

        result = {x.id: Decimal(0) for x in contracts}
        for contracts_slice in grouped_slice(contracts):
            query = payment.join(line,
                condition=(payment.line == line.id)
                ).select(line.contract, payment.kind, Sum(payment.amount),
                where=(line.contract.in_([x.id for x in contracts_slice])) &
                    (payment.state == 'processing'),
                group_by=[line.contract, payment.kind]
                )
            cursor.execute(*query)
            for contract, kind, amount in cursor.fetchall():
                if kind == 'receivable':
                    result[contract] -= amount
                elif kind == 'payable':
                    result[contract] += amount
        return result

    def invoices_report(self):
        # invoices_report must be generated with the real today
        # to calculate correctly the planned_payment_date
        with Transaction().set_context(
                    client_defined_date=datetime.date.today()):
            pool = Pool()
            ContractInvoice = pool.get('contract.invoice')
            all_invoices = ContractInvoice.search([
                    ('contract', '=', self),
                    ('invoice.state', 'not in', ('cancel', 'paid', 'draft'))])
            amount_per_date = defaultdict(
                lambda: {'amount': 0, 'components': []})
            taxes = defaultdict(int)
            for invoice in all_invoices:
                if invoice.invoice.lines_to_pay:
                    for line in invoice.invoice.lines_to_pay:
                        date = line.payment_date or line.maturity_date or \
                            line.date
                        amount_per_date[date]['amount'] += line.amount
                        amount_per_date[date]['components'].append({
                                'kind': 'line_to_pay', 'amount': line.amount,
                                'line': line, 'invoice': invoice,
                                'term': invoice.invoice.payment_term})
                else:
                    date = invoice.planned_payment_date or invoice.start \
                        or invoice.invoice.invoice_date
                    total_amount = invoice.invoice.total_amount
                    payment_term = invoice.invoice.payment_term
                    terms = payment_term.compute(total_amount,
                        self.get_currency(),
                        invoice.planned_payment_date or invoice.start
                        or invoice.invoice_date)
                    for date, term_amount in iter(terms):
                        amount_per_date[date]['amount'] += term_amount
                        amount_per_date[date]['components'].append({
                                'kind': 'invoice_term', 'amount': term_amount,
                                'term': invoice.invoice.payment_term,
                                'invoice': invoice})
                for tax in invoice.invoice.taxes:
                    taxes[tax.tax] += tax.amount
            invoices = [{
                    'total_amount': amount_per_date[key]['amount'],
                    'planned_payment_date': key,
                    'components': amount_per_date[key]['components']}
                for key in sorted(amount_per_date.keys())]
            total_amount = sum(x['total_amount'] for x in invoices)
            invoices = self.substract_balance_from_invoice_reports(invoices)
            total_amount_after_substract = sum(x['total_amount']
                for x in invoices)
            if total_amount != 0:
                ratio_taxes = total_amount_after_substract / total_amount
            else:
                ratio_taxes = 1
            taxes = {code: self.currency.round(amount * ratio_taxes)
                for code, amount in taxes.iteritems()}
            return [invoices, sum(x['total_amount'] for x in invoices), taxes]

    def substract_balance_from_invoice_reports(self, invoice_reports):
        outstanding_amount = self.balance_today - self.receivable_today
        outstanding_amount = min(0, outstanding_amount)
        outstanding_amount += self.processing_payments_amount
        if outstanding_amount >= 0:
            return invoice_reports
        for report in invoice_reports:
            if not outstanding_amount:
                break
            if abs(outstanding_amount) > report['total_amount']:
                outstanding_amount += report['total_amount']
                report['components'].append({
                        'kind': 'overpayment_substraction',
                        'amount': - report['total_amount']})
                report['total_amount'] = 0
            else:
                report['total_amount'] += outstanding_amount
                report['components'].append(
                    {'kind': 'overpayment_substraction', 'amount':
                        outstanding_amount})
                outstanding_amount = 0
        return invoice_reports

    def invoice_to_end_date(self):
        self.invoice([self], self.final_end_date)

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

        account_invoices, contract_invoices, payment_dates = \
            cls._calculate_aperiodic_invoices(contracts, frequency)

        cls._finalize_invoices(contract_invoices)

        AccountInvoice.save(account_invoices)
        ContractInvoice.save(contract_invoices)
        AccountInvoice.post(account_invoices)
        lines_to_write = []
        for i, p in zip(account_invoices, payment_dates):
            lines_to_write += [list(i.lines_to_pay), p]
        if lines_to_write:
            MoveLine.write(*lines_to_write)
        return contract_invoices

    @classmethod
    def _calculate_aperiodic_invoices(cls, contracts, frequency):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        Journal = pool.get('account.journal')
        journal, = Journal.search([
                ('type', '=', 'revenue'),
                ], limit=1)

        account_invoices = []
        contract_invoices = []
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
            lines = []
            for premium in premiums:
                lines.extend(premium.get_invoice_lines(None, None))
            contract.finalize_invoices_lines(lines)
            new_invoice.lines = lines
            contract_invoice = ContractInvoice(non_periodic=True,
                invoice=new_invoice, contract=contract, start=None, end=None)
            contract_invoices.append(contract_invoice)
            account_invoices.append(new_invoice)
            payment_dates.append({'payment_date': payment_date})
        return account_invoices, contract_invoices, payment_dates

    def check_billing_information(self):
        for billing in self.billing_informations:
            if billing.direct_debit and not billing.direct_debit_account:
                parent = coog_string.translate_label(
                    self, 'billing_information')
                field = coog_string.translate_label(billing,
                    'direct_debit_account')
                self.append_functional_error('child_field_required',
                    (field, parent))
            if not billing.payer and billing.direct_debit:
                self.append_functional_error('no_payer')

    @classmethod
    def get_billing_information(cls, contracts, names):
        pool = Pool()
        ContractBillingInformation = pool.get('contract.billing_information')
        return cls.get_revision_value(contracts, names,
            ContractBillingInformation)

    def load_billing_information(self):
        date = Transaction().context.get('contract_revision_date',
            ServerContext().get('contract_revision_date', utils.today()))
        return utils.get_good_version_at_date(self, 'billing_informations',
            at_date=date, start_var_name='date')

    @classmethod
    def get_last_invoice(cls, contracts, name):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        Invoice = pool.get('account.invoice')
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table = cls.__table__()
        contract_invoice = ContractInvoice.__table__()
        invoice = Invoice.__table__()
        values = dict.fromkeys((c.id for c in contracts))
        in_max = transaction.database.IN_MAX
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
            if billing_information.same_rule(next_billing_information):
                continue
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
        with ServerContext().set_context(
                cur_billing_information=billing_information):
            rule, until_date = billing_information.billing_mode.get_rrule(
                start, until)
        invoice_rrule.rrule(rule)
        return (invoice_rrule, until_date, billing_information)

    def get_invoice_periods(self, up_to_date, from_date=None):
        if not self.billing_informations:
            return []
        contract_end_date = self.activation_history[-1].end_date
        if from_date:
            start = max(from_date, self.start_date)
        elif self.last_invoice_end:
            start = self.last_invoice_end + relativedelta(days=+1)
        else:
            start = self.start_date
        if self.block_invoicing_until:
            start = max(start, self.block_invoicing_until)
        if up_to_date and start > up_to_date:
            return []
        periods = []
        while (up_to_date and start < up_to_date) or len(periods) < 1:
            original_start = start
            rule, until, billing_information = \
                self._get_invoice_rrule_and_billing_information(start)
            for date in rule:
                if hasattr(date, 'date'):
                    date = date.date()
                if date <= start:
                    continue
                end = date + relativedelta(days=-1)
                periods.append((start, min(end, contract_end_date or
                            datetime.date.max), billing_information))
                start = date
                if not up_to_date or start > up_to_date:
                    break
            if until and (up_to_date and until < up_to_date):
                if contract_end_date and contract_end_date < up_to_date:
                    if until > contract_end_date:
                        until = contract_end_date
                if start != until:
                    end = until + relativedelta(days=-1)
                    periods.append((start, end, billing_information))
                    start = until
                continue
            if start == original_start:
                if until and start <= until:
                    end = until + relativedelta(days=-1)
                    periods.append((start, end, billing_information))
                    start = until
                else:
                    raise NotImplementedError
        return periods

    @classmethod
    def clean_up_contract_invoices(cls, contracts, from_date=None,
            to_date=None, non_periodic=False):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        contract_invoices = []
        for contract_slice in grouped_slice(contracts):
            contract_invoices.extend(ContractInvoice.search([
                        [('invoice_state', '!=', 'cancel'),
                            ('contract', 'in', [x.id for x in contract_slice])],
                        ['OR',
                            ('contract.status', '=', 'void'),
                            ('start', '<=', to_date or datetime.date.min),
                            ('end', '>=', from_date or datetime.date.max)],
                        ]))
        actions = {
            'cancel': [],
            'delete': [],
            }
        for contract_invoice in contract_invoices:
            if contract_invoice.non_periodic and not non_periodic:
                continue
            actions[contract_invoice.cancel_or_delete()].append(
                contract_invoice)
        if actions['delete']:
            ContractInvoice.delete(actions['delete'])
        if actions['cancel']:
            ContractInvoice.cancel(actions['cancel'])

        rebill_data = ServerContext().get('rebill_data', None)
        if rebill_data is None:
            return

        cancelled_by_contract = {}

        def key(x):
            return x.contract.id
        cancelled = sorted(actions['cancel'], key=key)
        for contract_id, grouped in groupby(cancelled, key=key):
            by_date = defaultdict(list)
            for invoice in grouped:
                by_date[invoice.start or datetime.date.min].append(invoice)
            cancelled_by_contract[contract_id] = by_date
        rebill_data['cancelled_invoices'] = cancelled_by_contract

    def get_first_invoices_date(self):
        return max(self.start_date, utils.today())

    @classmethod
    def _first_invoice(cls, contracts, and_post=False):
        with Transaction().set_user(0, set_context=True):
            Invoice = Pool().get('account.invoice')
            # Make sure all existing invoices are cleaned up
            cls.clean_up_contract_invoices(contracts,
                from_date=datetime.date.min)
            contract_invoices = []
            for contract in contracts:
                invoices = cls.invoice([contract],
                    contract.get_first_invoices_date())
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

    def can_be_invoiced(self):
        if self.status not in ('active', 'quote', 'terminated'):
            if not (self.status == 'hold' and self.sub_status and
                    not self.sub_status.hold_billing):
                return False
        return True

    @classmethod
    def invoice(cls, contracts, up_to_date):
        'Invoice contracts up to the date'
        periods = defaultdict(list)
        for contract in contracts:
            if not contract.can_be_invoiced():
                continue
            cls._invoices_cache.set(contract.id, None)
            for period in contract.get_invoice_periods(min(up_to_date,
                        contract.activation_history[-1].end_date or
                        datetime.date.max)):
                periods[period].append(contract)
        return cls.invoice_periods(periods)

    @classmethod
    def invoice_periods(cls, periods):
        'Invoice periods for contracts'
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ContractInvoice = pool.get('contract.invoice')
        account_invoices, contract_invoices = cls._calculate_invoices(periods)
        cls._finalize_invoices(contract_invoices)
        Invoice.save(account_invoices)
        ContractInvoice.save(contract_invoices)
        return contract_invoices

    @classmethod
    def _calculate_invoices(cls, periods):
        pool = Pool()
        Journal = pool.get('account.journal')
        ContractInvoice = pool.get('contract.invoice')
        journals = Journal.search([
                ('type', '=', 'revenue'),
                ], limit=1)
        if journals:
            journal, = journals
        else:
            journal = None

        account_invoices = []
        contract_invoices = []
        for period in sorted(periods.iterkeys(), key=lambda x: x[0]):
            for contract in periods[period]:
                invoice = contract.get_invoice(*period)
                if not invoice.journal:
                    invoice.journal = journal
                invoice.lines = contract.get_invoice_lines(*period[0:2])
                account_invoices.append(invoice)
                contract_invoices.append(ContractInvoice(
                        contract=contract,
                        invoice=invoice,
                        start=period[0],
                        end=period[1]))
        return account_invoices, contract_invoices

    @classmethod
    def _finalize_invoices(cls, contract_invoices):
        for contract_invoice in contract_invoices:
            invoice = contract_invoice.invoice
            invoice.taxes = [x for x in invoice._compute_taxes().values()]
            if getattr(invoice, 'invoice_address', None) is None:
                invoice.invoice_address = \
                    contract_invoice.contract.get_contract_address(
                        max(contract_invoice.start or datetime.date.min,
                            utils.today()))
                if (invoice.invoice_address.party != invoice.party):
                    invoice.invoice_address = \
                        contract_invoice.contract.get_contract_address(
                            (contract_invoice.end + relativedelta(days=1)))
                    if (invoice.invoice_address.party != invoice.party):
                        invoice.invoice_address = invoice.party.main_address()

    @classmethod
    def premium_intervals_cache(cls):
        cache_holder = get_cache_holder()
        interval_cache = cache_holder.get('premium_intervals_cache')
        if interval_cache is None:
            interval_cache = CoogCache()
            cache_holder['premium_intervals_cache'] = interval_cache
        return interval_cache

    @classmethod
    def _search_premium_intervals(cls, contract, start, end):
        cache = cls.premium_intervals_cache()
        tree = cache.get(contract.id)
        if tree is None:
            tree = intervaltree.IntervalTree((
                    intervaltree.Interval(p.start or datetime.date.min,
                        coog_date.add_day(p.end, 1) if p.end
                        else datetime.date.max, idx)
                    for idx, p in enumerate(contract.all_premiums)))
            cache[contract.id] = tree
        if tree is not None:
            return [contract.all_premiums[x.data]
                for x in tree.search(start, coog_date.add_day(end, 1))]

    @classmethod
    def calculate_prices(cls, contracts, start=None, end=None):
        cls.premium_intervals_cache().clear()
        for contract in contracts:
            cls._future_invoices_cache.set(contract.id, {})
        return super(Contract, cls).calculate_prices(contracts, start, end)

    def get_invoice(self, start, end, billing_information):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        lang = self.company.party.lang
        if not lang:
            self.company.raise_user_error('missing_lang',
                {'party': self.company.rec_name})
        cancelled = self.get_cancelled_invoice_in_rebill(start)
        payment_term = cancelled.invoice.payment_term if cancelled else \
            billing_information.payment_term
        return Invoice(
            invoice_address=None,  # Will be really set in finalize invoice
            contract=self,
            company=self.company,
            type='out',
            business_kind='contract_invoice',
            journal=None,
            party=self.subscriber,
            currency=self.currency,
            account=self.subscriber.account_receivable_used,
            payment_term=payment_term,
            state='validated',
            invoice_date=start,
            accounting_date=None,
            description='%s (%s - %s)' % (
                self.rec_name,
                lang.strftime(start, lang.code, lang.date) if start else '',
                lang.strftime(end, lang.code, lang.date) if end else '',
                ),
            )

    def get_cancelled_invoice_in_rebill(self, date):
        rebill_data = ServerContext().get('rebill_data', {})
        if not rebill_data:
            return
        cancelled_invoices = rebill_data.get('cancelled_invoices', {})
        invoices_for_contract = cancelled_invoices.get(self.id, {})
        date_invoices = invoices_for_contract.get(date, [])
        if date_invoices and len(date_invoices) == 1:
            return date_invoices[0]

    def finalize_invoices_lines(self, lines):
        for line in lines:
            line.company = self.company

    def get_invoice_lines(self, start, end):
        lines = self.compute_invoice_lines(start, end)
        self.finalize_invoices_lines(lines)
        return lines

    def compute_invoice_lines(self, start, end):
        lines = []
        for premium in self._search_premium_intervals(self, start, end):
            # Force set main_contract to avoid the getter cost
            premium.main_contract = self
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
        if last_posted:
            return max(last_posted[0].start, utils.today())

    @classmethod
    def rebill_contracts(cls, contracts, start, end=None, post_end=None):
        for contract in contracts:
            contract.rebill(start, end, post_end)

    def rebill(self, start, end=None, post_end=None):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        rebill_data = ServerContext().get('rebill_data', {})

        with ServerContext().set_context(rebill_data=rebill_data):
            # Store the end date of the last invoice to be able to
            # know up til when we should rebill

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

    def is_invoiced_to_end(self):
        return self.last_invoice_end and self.last_invoice_end >= self.end_date

    def invoice_next_period(self):
        pool = Pool()
        Contract = pool.get('contract')
        if self.is_invoiced_to_end():
            return
        if self.last_invoice_end:
            to_date = coog_date.add_day(self.last_invoice_end, 1)
        else:
            to_date = self.start_date
        new_invoice, = Contract.invoice([self], to_date)
        return new_invoice

    def invoice_against_balance(self, ignore_payments=False):
        balance = self.balance + sum(x.invoice.total_amount
            for x in self.invoices if x.invoice.state == 'validated')
        if not ignore_payments:
            Payment = Pool().get('account.payment')
            payable_payments = [x for x in Payment.search([
                        ('line.contract', '=', self),
                        ('state', 'in', ['approved', 'draft']),
                        ('kind', '=', 'payable')])]
            if payable_payments:
                balance += sum(x.amount for x in payable_payments)
        next_date = self.last_invoice_end or self.initial_start_date
        while balance < 0 and next_date < self.end_date:
            new_invoice = self.invoice_next_period()
            if not new_invoice:
                break
            balance += new_invoice.invoice.total_amount
            next_date = coog_date.add_day(new_invoice.end, 1)   # NOQA

    @classmethod
    def get_line_reconciliation_per_contract(cls, contracts, limit_date):
        """
        Returns a list of lines per contracts which can be reconciled
        """
        if not contracts:
            return {}
        MoveLine = Pool().get('account.move.line')
        date = Transaction().context.get('reconcile_to_date',
            utils.today())
        subscribers = defaultdict(list)
        for contract in contracts:
            subscribers[contract.subscriber].append(contract)
        clause = [
            ('reconciliation', '=', None),
            ('move_state', 'not in', ('draft', 'validated'))]
        if limit_date:
            clause.append(('date', '<=', date))

        sub_clause = ['OR']
        for subscriber, contract_group in subscribers.iteritems():
            sub_clause.append([
                    ('party', '=', subscriber.id),
                    ('account', '=', subscriber.account_receivable_used.id),
                    ('contract', 'in', [x.id for x in contract_group]),
                    ])
        clause.append(sub_clause)
        may_be_reconciled = MoveLine.search(clause,
            order=[('contract', 'ASC')])

        per_contract = defaultdict(list)
        for line in may_be_reconciled:
            per_contract[line.contract].append(line)

        return per_contract

    @classmethod
    def get_lines_to_reconcile(cls, contracts, limit_date=True):
        """
        Returns list of line reconciliations packets to be reconciled
        together.
        """
        MoveLine = Pool().get('account.move.line')

        # Get non-reconciled lines per contract
        lines_per_contract = cls.get_line_reconciliation_per_contract(
            contracts, limit_date)
        return MoveLine.get_reconciliation_lines(lines_per_contract)

    @dualmethod
    def reconcile(cls, contracts, limit_date=True):
        pool = Pool()
        Reconciliation = pool.get('account.move.reconciliation')
        return Reconciliation.create_reconciliations_from_lines(
            cls.get_lines_to_reconcile(contracts, limit_date))

    @fields.depends('billing_informations')
    def on_change_product(self):
        super(Contract, self).on_change_product()

    def init_from_product(self, product):
        super(Contract, self).init_from_product(product)
        if not self.product or not self.product.billing_modes:
            return
        self.init_billing_information()

    def init_billing_information(self):
        if getattr(self, 'billing_informations', None):
            return
        BillingInformation = Pool().get('contract.billing_information')
        default_billing_mode = self.product.billing_modes[0]
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
        with Transaction().new_transaction() as transaction:
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
                transaction.rollback()
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
        '''
        we want to rebill void contract from its start date
        '''
        previous_dates = {x.id: x.end_date if x.status != 'void'
            else x.start_date for x in contracts}
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

    @classmethod
    def calculate_prices_after_renewal(cls, contracts,
            new_start_date=None, caller=None):
        pool = Pool()
        Contract = pool.get('contract')
        Contract.calculate_prices(contracts, start=new_start_date)

    @classmethod
    def _post_renew_methods(cls):
        methods = super(Contract, cls)._post_renew_methods()
        methods |= {'calculate_prices_after_renewal'}
        methods |= {'rebill_after_renewal'}
        return methods

    @classmethod
    def rebill_after_renewal(cls, contracts, new_start_date=None, caller=None):
        for contract in contracts:
            contract.invoice_to_end_date()

    @classmethod
    def _pre_renew_methods(cls):
        methods = super(Contract, cls)._pre_renew_methods()
        methods |= {'check_contract_invoices_before_renewal'}
        return methods

    @classmethod
    def check_contract_invoices_before_renewal(cls, contracts,
            new_start_date=None, caller=None):
        for contract in contracts:
            if getattr(contract, 'last_posted_invoice_end', None) is not None:
                if not (contract.last_posted_invoice_end ==
                        contract.activation_history[-1].end_date):
                    cls.raise_user_error('missing_invoices')

    @classmethod
    def do_decline(cls, contracts, reason):
        super(Contract, cls).do_decline(contracts, reason)
        cls.clean_up_contract_invoices(contracts, from_date=datetime.date.min)

    ###########################################################################
    # Cached invoices calculation to speed up future payments wizard,         #
    # report generation, & co                                                 #
    ###########################################################################
    @classmethod
    def get_future_invoices(cls, contract, from_date=None, to_date=None):
        if isinstance(contract, int):
            contract = cls(contract)
        cached = cls._future_invoices_cache.get(contract.id, {}) or {}
        sub_key = hash(cls._future_invoices_cache_key())
        if sub_key in cached:
            invoices = cls.load_from_cached_invoices(cached[sub_key])
        else:
            periods = {x: [contract]
                for x in contract.get_invoice_periods(
                    contract.end_date or to_date, contract.start_date)}
            _, contract_invoices = contract._calculate_invoices(periods)
            invoices = contract.dump_future_invoices(contract_invoices)
            cached[sub_key] = cls.dump_to_cached_invoices(invoices)
            cls._future_invoices_cache.set(contract.id, cached)
        return [x for x in invoices
            if x['end'] >= (from_date or datetime.date.min)
            and x['start'] <= (to_date or datetime.date.max)]

    @classmethod
    def _future_invoices_cache_key(cls):
        context = Transaction().context
        return (context.get('company', ''), context.get('language', ''))

    @classmethod
    def load_from_cached_invoices(cls, cache):
        ContractPremium = Pool().get('contract.premium')
        invoices, premium_ids = cache['invoices'], cache['premium_ids']
        premium_per_id = {x.id: x for x in ContractPremium.browse(premium_ids)}
        for invoice in invoices:
            for line in invoice['details']:
                if line['premium'] is None:
                    continue
                line['premium'] = premium_per_id[line['premium']]
        return invoices

    @classmethod
    def dump_to_cached_invoices(cls, future_invoices):
        premium_ids = set([])
        invoices_copy = []
        for invoice in future_invoices:
            invoice_copy = invoice.copy()
            invoices_copy.append(invoice_copy)
            invoice_copy['details'] = []
            for line in invoice['details']:
                line_copy = line.copy()
                if line_copy['premium'] is not None:
                    line_copy['premium'] = line_copy['premium'].id
                    premium_ids.add(line_copy['premium'])
                invoice_copy['details'].append(line_copy)
        return {'invoices': invoices_copy, 'premium_ids': list(premium_ids)}

    def dump_future_invoices(self, contract_invoices):
        lines = []
        for contract_invoice in contract_invoices:
            lines.append(self.new_future_invoice(contract_invoice))
            self.set_future_invoice_lines(contract_invoice, lines[-1])
        return lines

    def new_future_invoice(self, contract_invoice):
        invoice = contract_invoice.invoice
        return {
            'name': invoice.description,
            'start': contract_invoice.start,
            'end': contract_invoice.end,
            'currency_digits': invoice.currency.digits,
            'currency_symbol': invoice.currency.symbol,
            'premium': None,
            'amount': Decimal(0),
            'tax_amount': Decimal(0),
            'fee': Decimal(0),
            'total_amount': Decimal(0),
            'details': [],
            }

    def set_future_invoice_lines(self, contract_invoice, displayer):
        pool = Pool()
        Tax = pool.get('account.tax')
        config = pool.get('account.configuration')(1)
        invoice = contract_invoice.invoice
        for line in sorted(invoice.lines, key=lambda x: (
                    getattr(x.details[0].premium, 'rec_name', ''),
                    x.coverage_start)):
            taxes = Tax.compute(line.taxes, line.unit_price, line.quantity,
                date=contract_invoice.start)
            premium = line.details[0].premium
            amount = invoice.currency.round(line.unit_price)
            if config.tax_rounding == 'line':
                # Manually handle taxes_included_in_premium, it's easier since
                # we only need to manage a single total tax amount.
                if premium.rated_entity and getattr(premium.rated_entity,
                        'taxes_included_in_premium', False):
                    tax_amount = invoice.currency.round(line.unit_price +
                        sum(t['amount'] for t in taxes)) - amount
                else:
                    tax_amount = sum(
                        invoice.currency.round(t['amount'])
                        for t in taxes)
            else:
                tax_amount = invoice.currency.round(
                    sum(t['amount'] for t in taxes))
            displayer['details'].append({
                    'name': premium.rec_name,
                    'start': line.coverage_start,
                    'end': line.coverage_end,
                    'premium': premium,
                    'currency_digits': invoice.currency.digits,
                    'currency_symbol': invoice.currency.symbol,
                    'amount': amount if not premium.fee else 0,
                    'fee': amount if premium.fee else 0,
                    'tax_amount': tax_amount,
                    'total_amount': amount + tax_amount,
                    })
            displayer['tax_amount'] += tax_amount
            displayer['total_amount'] += amount + tax_amount
            if premium.fee:
                displayer['fee'] += amount
            else:
                displayer['amount'] += amount
    ###########################################################################
    # End calculation cache                                                   #
    ###########################################################################


class ContractFee:
    __metaclass__ = PoolMeta
    __name__ = 'contract.fee'

    active = fields.Boolean('Active')

    @classmethod
    def default_active(cls):
        return True

    @classmethod
    def delete(cls, contract_fees):
        to_deactivate = []
        contract_fee_dict = {x.id: x for x in contract_fees}

        cursor = Transaction().connection.cursor()
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
    __metaclass__ = PoolMeta
    __name__ = 'contract.option'

    @classmethod
    def delete(cls, options):
        to_decline = []
        option_dict = {x.id: x for x in options}

        cursor = Transaction().connection.cursor()
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

    def get_paid_amount_at_date(self, date):
        pool = Pool()
        contract_invoice = pool.get('contract.invoice').__table__()
        invoice = pool.get('account.invoice').__table__()
        invoice_line = pool.get('account.invoice.line').__table__()
        detail = pool.get('account.invoice.line.detail').__table__()
        query_table = detail.join(invoice_line,
            condition=invoice_line.id == detail.invoice_line,
            ).join(invoice, condition=invoice.id == invoice_line.invoice
            ).join(contract_invoice,
            condition=contract_invoice.invoice == invoice.id)
        cursor = Transaction().connection.cursor()
        cursor.execute(*query_table.select(Sum(invoice_line.unit_price),
                where=(invoice.state == 'paid')
                & (contract_invoice.start <= date)
                & (detail.option == self.id)))
        return cursor.fetchone()[0]


class ExtraPremium:
    __metaclass__ = PoolMeta
    __name__ = 'contract.option.extra_premium'

    active = fields.Boolean('Active')

    @classmethod
    def default_active(cls):
        return True

    @classmethod
    def delete(cls, extra_premiums):
        to_deactivate = []
        extra_premium_dict = {x.id: x for x in extra_premiums}

        cursor = Transaction().connection.cursor()
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


class ContractBillingInformation(model._RevisionMixin, model.CoogSQL,
        model.CoogView):
    'Contract Billing Information'

    __name__ = 'contract.billing_information'
    _parent_name = 'contract'
    _func_key = 'date'

    contract = fields.Many2One('contract', 'Contract', required=True,
        select=True, ondelete='CASCADE')
    contract_status = fields.Function(
        fields.Char('Contract Status'),
        'on_change_with_contract_status')
    billing_mode = fields.Many2One('offered.billing_mode', 'Billing Mode',
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS,
        required=True, ondelete='RESTRICT')
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', ondelete='RESTRICT', states={
            'required': And(Eval('direct_debit', False),
                (Eval('_parent_contract', {}).get('status', '') == 'active')),
            'invisible': Len(Eval('possible_payment_terms', [])) < 2,
            'readonly': Bool(Eval('contract_status')) & (
                Eval('contract_status') != 'quote'),
            },
        domain=[('id', 'in', Eval('possible_payment_terms'))],
        depends=['possible_payment_terms', 'contract_status'])
    direct_debit = fields.Function(
        fields.Boolean('Direct Debit Payment'), 'on_change_with_direct_debit',
        searcher='search_direct_debit')
    direct_debit_day_selector = fields.Function(
        fields.Selection('get_allowed_direct_debit_days',
            'Direct Debit Day', states={
                'invisible': ~Eval('direct_debit', False),
                'required': And(Eval('direct_debit', False),
                    (Eval('_parent_contract', {}).get('status', '') ==
                        'active')),
                'readonly': Bool(Eval('contract_status')) & (
                    Eval('contract_status') != 'quote'),
                }, sort=False,
            depends=['direct_debit', 'direct_debit_day', 'contract_status']),
        'get_direct_debit_day_selector', 'setter_void')
    direct_debit_day = fields.Integer('Direct Debit Day',
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS)
    direct_debit_account = fields.Many2One('bank.account',
        'Direct Debit Account', states={
            'invisible': ~Eval('direct_debit'),
            'readonly': Bool(Eval('contract_status')) & (
                Eval('contract_status') != 'quote'),
            }, depends=['direct_debit', 'contract_status'],
        ondelete='RESTRICT')
    possible_payment_terms = fields.Function(fields.One2Many(
            'account.invoice.payment_term', None, 'Possible Payment Term'),
            'on_change_with_possible_payment_terms')
    is_once_per_contract = fields.Function(
        fields.Boolean('Once Per Contract?'),
        'on_change_with_is_once_per_contract')
    payer = fields.Many2One('party.party', 'Payer', states={
            'invisible': ~Eval('direct_debit'),
            'required': And(Bool(Eval('direct_debit', False)),
                (Eval('_parent_contract', {}).get('status', '') ==
                    'active')),
            'readonly': Bool(Eval('contract_status')) & (
                    Eval('contract_status') != 'quote'),

            }, depends=['direct_debit', 'contract_status'],
            ondelete='RESTRICT')
    suspended = fields.Function(fields.Boolean('Suspended'),
        'get_suspended')
    icon = fields.Function(fields.Char('Icon'),
        'get_icon')
    suspensions = fields.One2Many('contract.payment_suspension',
        'billing_info', 'Suspensions', delete_missing=True)

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
        cls.direct_debit_account.domain.append([
                'owners', '=', Eval('payer')
                ])
        cls.direct_debit_account.depends.append('payer')
        cls._buttons.update({
                'suspend_payments': {'invisible': Or(~Eval('direct_debit'),
                        Bool(Eval('suspended')))},
                'unsuspend_payments': {'invisible': Or(~Eval('direct_debit'),
                        ~Bool(Eval('suspended')))},
                })
        cls.date.states = _CONTRACT_STATUS_STATES
        cls.date.depends = _CONTRACT_STATUS_DEPENDS

    @classmethod
    def suspension_values(cls, billing_id, payment, **kwargs):
        values = {
            'billing_info': billing_id,
            'payment_line_due': payment.line.id if payment else None,
            }
        values.update(kwargs)
        return values

    @classmethod
    @model.CoogView.button
    def suspend_payments(cls, billings, payments_per_billing=None):
        if not billings and not payments_per_billing:
            return
        BillingSuspension = Pool().get('contract.payment_suspension')
        values = []
        if payments_per_billing:
            server_ctx = ServerContext()
            for billing_id, payments in payments_per_billing.items():
                for payment in payments:
                    values.append(cls.suspension_values(
                            billing_id, payment,
                            use_force=server_ctx.get('use_force', False),
                            force_active=server_ctx.get('use_force', False)))
        else:
            values += [cls.suspension_values(x.id, None, use_force=True,
                    force_active=True) for x in billings]
        if values:
            BillingSuspension.create(values)

    @classmethod
    @model.CoogView.button
    def unsuspend_payments(cls, billings):
        PaymentSuspension = Pool().get('contract.payment_suspension')
        suspensions = PaymentSuspension.search([('billing_info', 'in',
                    [x.id for x in billings])])
        PaymentSuspension.write(suspensions, {
                'use_force': True,
                'force_active': False,
                })

    @classmethod
    def get_suspended(cls, billings, name):
        res = {x.id: False for x in billings}
        suspensions = Pool().get('contract.payment_suspension').search(
            [('billing_info', 'in', [x.id for x in billings])],
            order=[('billing_info', 'ASC')])

        for billing_info, suspensions in groupby(suspensions,
                key=lambda x: x.billing_info.id):
            res[billing_info] = any(suspensions)
        return res

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.1: Billing change
        migrate = False
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        if (not TableHandler.table_exist(
                    'contract_billing_information')
                and TableHandler.table_exist('contract_invoice_frequency')):
            migrate = True
        # Migration from 1.8: Add payer on billing information
        add_payer = False
        contract_billing_h = TableHandler(cls, module_name)
        if not contract_billing_h.column_exist('payer'):
            add_payer = True

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

        # Migration from 1.8: Add payer on billing information
        # The default payer is the mandate's party
        if add_payer:
            cls._migrate_payer()

    @classmethod
    def _migrate_payer(cls):
        # Migrate from 1.8: Add payer
        # payer is set as contract subscriber
        # overriden in account_payment_sepa_contract to migrate payer from SEPA
        # mandate
        pool = Pool()
        cursor = Transaction().connection.cursor()
        Contract = pool.get('contract')
        contract_table = Contract.__table__()
        contract_billing = pool.get('contract.billing_information').__table__()
        update_data = contract_billing.join(contract_table, condition=(
                contract_billing.contract == contract_billing.id)
            ).select(contract_billing.id.as_('billing_info'),
                contract_table.subscriber)

        cursor.execute(*contract_billing.update(
                columns=[contract_billing.payer],
                values=[update_data.subscriber],
                from_=[update_data],
                where=(contract_billing.id == update_data.billing_info)))

    @staticmethod
    def revision_columns():
        return ['billing_mode', 'payment_term', 'direct_debit_day',
            'direct_debit_account', 'payer']

    @classmethod
    def get_reverse_field_name(cls):
        return 'billing_information'

    def get_icon(self, name=None):
        if self.suspended:
            return 'rounded_warning'
        return super(ContractBillingInformation, self).get_icon(name)

    @fields.depends('billing_mode')
    def get_allowed_direct_debit_days(self):
        if not self.billing_mode:
            return [('', '')]
        return self.billing_mode.get_allowed_direct_debit_days()

    def get_direct_debit_day_selector(self, name=None):
        if not self.billing_mode.direct_debit:
            return ''
        return str(self.direct_debit_day)

    @fields.depends('direct_debit_account', 'payer')
    def on_change_payer(self):
        if not self.payer or self.direct_debit_account and (self.payer not in
                self.direct_debit_account.owners):
            self.direct_debit_account = None

    @fields.depends('billing_mode', 'direct_debit_day',
        'direct_debit_day_selector', 'direct_debit_account')
    def on_change_billing_mode(self):
        if not self.billing_mode or not self.billing_mode.direct_debit:
            self.direct_debit_day = None
            self.direct_debit_day_selector = ''
            self.direct_debit_account = None
            return
        if (self.billing_mode.direct_debit and
                (str(self.direct_debit_day), str(self.direct_debit_day))
                not in self.billing_mode.get_allowed_direct_debit_days()):
            self.direct_debit_day = int(
                self.billing_mode.get_allowed_direct_debit_days()[0][0])
            self.direct_debit_day_selector = \
                self.get_direct_debit_day_selector()

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

    @fields.depends('contract')
    def on_change_with_contract_status(self, name=None):
        # Fake billing information could be displayed in endorsement so
        # we need to check if this is a real billing information
        return self.contract.status if self.contract and self.id > 0 else ''

    def get_direct_debit_planned_date(self, line):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        if not (self.direct_debit and self.direct_debit_day):
            return None
        if type(line) == dict:
            cur_line = MoveLine(**line)
        else:
            cur_line = line
        payment_journal = cur_line.get_payment_journal()
        return payment_journal.get_next_possible_payment_date(cur_line,
            self.direct_debit_day)

    def same_rule(self, other):
        return self.billing_mode == other.billing_mode and \
            self.payment_term == other.payment_term

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values.get('date', None)

    @classmethod
    def search_direct_debit(cls, name, domain):
        return [('billing_mode.direct_debit',) + tuple(domain[1:])]


class Premium:
    __metaclass__ = PoolMeta
    __name__ = 'contract.premium'

    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('company', '=', Eval('context', {}).get('company', -1)),
            ['OR', [('kind', '=', 'revenue')], [('kind', '=', 'other')]]
            ],
        ondelete='RESTRICT', readonly=True)

    @classmethod
    def _export_light(cls):
        return super(Premium, cls)._export_light() | {'account'}

    def same_value(self, other):
        result = super(Premium, self).same_value(other)
        return result and self.account == other.account

    @property
    def prorate_premiums(self):
        return Pool().get(
            'offered.configuration').get_cached_prorate_premiums()

    @classmethod
    def new_line(cls, line, start_date, end_date):
        new_line = super(Premium, cls).new_line(line, start_date, end_date)
        if not new_line:
            return None
        new_line.account = line.account
        return new_line

    def get_description(self):
        return getattr(self.parent, 'full_name', self.parent.rec_name)

    def get_amount(self, start, end, frequency=None, amount=None,
            sync_date=None, interval_start=None, proportion=None,
            recursion=False):
        frequency = frequency or self.frequency
        amount = amount if amount is not None else self.amount
        proportion = proportion if proportion is not None \
            else self.prorate_premiums
        sync_date = sync_date or self.main_contract.start_date
        recursion = False
        interval_start = interval_start or self.start
        return utils.get_prorated_amount_on_period(start, end, frequency,
            amount, sync_date, interval_start, proportion, recursion)

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
        if self._round_unit_price_to_currency():
            line_amount = self.main_contract.company.currency.round(
                line_amount)
        else:
            # Round to maximum allowed precision
            line_amount = line_amount.quantize(
                Decimal(1) / 10 ** InvoiceLine.unit_price.digits[1])
        return [InvoiceLine(
                type='line',
                description=self.get_description(),
                origin=self.main_contract,
                quantity=1,
                unit=None,
                unit_price=line_amount,
                taxes=self.taxes,
                invoice_type='out',
                account=self.account,
                coverage_start=start,
                coverage_end=end,
                details=[InvoiceLineDetail.new_detail_from_premium(self)],
                )]

    def _round_unit_price_to_currency(self):
        return not self.main_contract.product.taxes_included_in_premium


class ContractInvoice(model.CoogSQL, model.CoogView):
    'Contract Invoice'

    __name__ = 'contract.invoice'

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
                'button_reinvoice': {
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

    def get_rec_name(self, name):
        return self.invoice.rec_name

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
                    'party': billing_info.payer,
                    'contract': self.contract,
                    })

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
        cursor = Transaction().connection.cursor()
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
    def reinvoice(cls, contract_invoices):
        pool = Pool()
        Contract = pool.get('contract')
        for contract_invoice in contract_invoices:
            assert contract_invoice.invoice_state != 'cancel'
        cls.cancel(contract_invoices)
        periods = defaultdict(list)
        for contract_invoice in contract_invoices:
            contract = contract_invoice.contract
            for period in contract.get_invoice_periods(contract_invoice.end,
                    contract_invoice.start):
                periods[period].append(contract)
        return Contract.invoice_periods(periods)

    @classmethod
    @model.CoogView.button
    def button_reinvoice(cls, contract_invoices):
        cls.reinvoice(contract_invoices)

    @classmethod
    @model.CoogView.button
    def cancel(cls, contract_invoices):
        Invoice = Pool().get('account.invoice')
        Invoice.cancel([x.invoice for x in contract_invoices])

    @classmethod
    def delete(cls, contract_invoices):
        Invoice = Pool().get('account.invoice')
        Invoice.delete([x.invoice for x in contract_invoices])
        super(ContractInvoice, cls).delete(contract_invoices)

    def cancel_or_delete(self):
        if self.invoice_state in ('validated', 'draft'):
            return 'delete'
        return 'cancel'

    def get_cancelled_in_rebill(self):
        return self.contract.get_cancelled_invoice_in_rebill(self.start) if \
            self.contract else None


class InvoiceContractStart(model.CoogView):
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
    invoice = StateAction('contract_insurance_invoice.act_premium_notice_form')

    def default_start(self, name):
        if Transaction().context.get('active_model', '') != 'contract':
            return {}
        if len(Transaction().context.get('active_ids', [])) != 1:
            return {}
        pool = Pool()
        Contract = pool.get('contract')
        contract = Contract(Transaction().context.get('active_ids')[0])
        if contract.last_invoice_end:
            date = coog_date.add_day(contract.last_invoice_end, 1)
        else:
            date = contract.initial_start_date
        if contract.block_invoicing_until:
            date = max(date, contract.block_invoicing_until)
        return {
            'up_to_date': date,
            }

    def do_invoice(self, action):
        pool = Pool()
        Contract = pool.get('contract')
        contracts = Contract.browse(Transaction().context['active_ids'])
        invoices = Contract.invoice(contracts, self.start.up_to_date)
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('id', 'in', [i.invoice.id for i in invoices])])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}


class DisplayContractPremium:
    __metaclass__ = PoolMeta
    __name__ = 'contract.premium.display'

    @classmethod
    def get_children_fields(cls):
        children = super(DisplayContractPremium, cls).get_children_fields()
        children['contract'].append('covered_elements')
        children['contract.covered_element'] = ['options']
        children['options'].append('extra_premiums')
        return children


class ContractSubStatus:
    __metaclass__ = PoolMeta
    __name__ = 'contract.sub_status'

    hold_billing = fields.Boolean('Hold Billing', depends=['status'],
        states={'invisible': Eval('status') != 'hold'})
