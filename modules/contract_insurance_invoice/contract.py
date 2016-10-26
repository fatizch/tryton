# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import intervaltree
import datetime
import calendar
import logging
import traceback
from collections import defaultdict
from decimal import Decimal

from sql import Column, Null, Literal
from sql.aggregate import Max, Count, Sum
from sql.conditionals import Coalesce

from dateutil.rrule import rrule, rruleset, MONTHLY, DAILY
from dateutil.relativedelta import relativedelta

from trytond.pool import Pool, PoolMeta
from trytond.model import dualmethod
from trytond.pyson import Eval, And, Len, If, Bool, PYSONEncoder
from trytond.error import UserError
from trytond import backend
from trytond.transaction import Transaction
from trytond.tools import reduce_ids, grouped_slice
from trytond.wizard import Wizard, StateView, Button, StateAction
from trytond.rpc import RPC
from trytond.cache import Cache

from trytond.modules.coog_core import (coog_date, coog_string, utils, model,
    fields)
from trytond.modules.coog_core.cache import CoogCache, get_cache_holder
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
                })
        cls._error_messages.update({
                'no_payer': 'A payer must be specified',
                })

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
        if not new_billing_information.payer:
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
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        non_periodic_invoices = ContractInvoice.search([
                ('contract', '=', self),
                ('invoice.state', 'not in', ('cancel', 'paid')),
                ('non_periodic', '=', True)])
        all_good_invoices = list(set(self.current_term_invoices) |
            set(non_periodic_invoices))
        amount_per_date = defaultdict(lambda: {'amount': 0, 'components': []})
        for invoice in all_good_invoices:
            if invoice.invoice.lines_to_pay:
                for line in invoice.invoice.lines_to_pay:
                    date = line.payment_date or line.maturity_date or line.date
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
        invoices = [{
                'total_amount': amount_per_date[key]['amount'],
                'planned_payment_date': key,
                'components': amount_per_date[key]['components']}
            for key in sorted(amount_per_date.keys())]
        invoices = self.substract_balance_from_invoice_reports(invoices)
        return [invoices, sum([x['total_amount'] for x in invoices])]

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
        Contract.invoice([self], self.final_end_date)

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
        rule, until_date = billing_information.billing_mode.get_rrule(start,
            until)
        invoice_rrule.rrule(rule)
        return (invoice_rrule, until_date, billing_information)

    def get_invoice_periods(self, up_to_date, from_date=None):
        contract_end_date = self.activation_history[-1].end_date
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

    @classmethod
    def invoice(cls, contracts, up_to_date):
        'Invoice contracts up to the date'
        periods = defaultdict(list)
        for contract in contracts:
            if contract.status not in ('active', 'quote', 'terminated'):
                if not (contract.status == 'hold' and contract.sub_status and
                        not contract.sub_status.hold_billing):
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
        return Invoice(
            invoice_address=None,  # Will be really set in finalize invoice
            contract=self,
            company=self.company,
            type='out',
            business_kind='contract_invoice',
            journal=None,
            party=self.subscriber,
            currency=self.currency,
            account=self.subscriber.account_receivable,
            payment_term=billing_information.payment_term,
            state='validated',
            invoice_date=start,
            accounting_date=None,
            description='%s (%s - %s)' % (
                self.rec_name,
                lang.strftime(start, lang.code, lang.date) if start else '',
                lang.strftime(end, lang.code, lang.date) if end else '',
                ),
            )

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
        date = Transaction().context.get('reconcile_to_date',
            utils.today())
        for contract in contracts:
            subscribers[contract.subscriber].append(contract)
        clause = [
            ('reconciliation', '=', None),
            ('date', '<=', date),
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
            order=[('contract', 'ASC')])

        per_contract = defaultdict(list)
        for line in may_be_reconciled:
            per_contract[line.contract].append(line)

        reconciliations = {}
        for contract, possible_lines in per_contract.iteritems():
            reconciliations[contract], possible_lines = \
                contract.reconcile_perfect_lines(possible_lines)

            if not possible_lines:
                continue

            possible_lines.sort(key=cls.key_func_for_reconciliation_order())

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

            reconciliations[contract].append((to_reconcile,
                    max(0, -total_to_reconcile)))

        # Split lines if necessary
        splits = MoveLine.split_lines([(lines[-1], split_amount)
                for (lines, split_amount) in sum(reconciliations.values(), [])
                if split_amount != 0])

        reconciliation_lines = []
        for contract, groups in reconciliations.iteritems():
            for lines, split_amount in groups:
                reconciliation_lines.append(lines)
                if split_amount == 0:
                    continue

                # If a line was split, add the matching line to the
                # reconciliation
                _, remaining, compensation = splits[lines[-1]]
                lines += [remaining, compensation]

        return reconciliation_lines

    def reconcile_perfect_lines(self, possible_lines):
        per_invoice = defaultdict(
            lambda: {'base': [], 'paid': [], 'canceled': []})
        unmatched = []
        for line in possible_lines:
            if not line.origin:
                unmatched.append(line)
                continue
            if (line.origin.__name__ == 'account.invoice' and
                    line.origin.move == line.move):
                per_invoice[line.origin]['base'].append(line)
                continue
            if (line.origin.__name__ == 'account.move' and
                    line.origin.origin.__name__ == 'account.invoice' and
                    line.origin.origin.cancel_move == line.move):
                per_invoice[line.origin.origin]['canceled'].append(line)
                continue
            if (line.origin.__name__ == 'account.payment' and
                    line.origin.line and
                    line.origin.line.origin.__name__ == 'account.invoice' and
                    line.origin.line.origin.move == line.origin.line.move):
                per_invoice[line.origin.line.origin]['paid'].append(line)
                continue
            unmatched.append(line)

        matched = []
        for data in per_invoice.values():
            base_lines, cancel_lines, pay_lines = [data[x] for x in
                'base', 'canceled', 'paid']
            if cancel_lines:
                if not base_lines:
                    unmatched.extend(cancel_lines + pay_lines)
                    continue
                base_and_cancel = base_lines + cancel_lines
                assert sum(x.amount for x in base_and_cancel) == 0
                matched.append((base_and_cancel, 0))
                unmatched.extend(pay_lines)
                continue
            if pay_lines:
                per_line = {x.origin.line: x for x in pay_lines}
                for line in base_lines:
                    if line not in per_line:
                        unmatched.append(line)
                        continue
                    if per_line[line].amount + line.amount != 0:
                        unmatched.extend([line, per_line.pop(line)])
                        continue
                    matched.append(([line, per_line.pop(line)], 0))
                unmatched.extend(per_line.values())
            if base_lines and not cancel_lines and not pay_lines:
                unmatched.extend(base_lines)
        return (matched, unmatched)

    @classmethod
    def key_func_for_reconciliation_order(cls):
        def get_key(x):
            if x.origin and x.origin.__name__ == 'account.invoice':
                return x.origin.start or x.date
            return x.date
        return get_key

    @dualmethod
    def reconcile(cls, contracts):
        pool = Pool()
        Reconciliation = pool.get('account.move.reconciliation')
        lines_to_reconcile, reconciliations = [], []
        lines_to_reconcile = cls.get_lines_to_reconcile(contracts)
        for reconciliation_lines in lines_to_reconcile:
            if not reconciliation_lines:
                continue
            reconciliations.append(Reconciliation(lines=reconciliation_lines,
                    date=max(x.date for x in reconciliation_lines)))
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
                for x in contract.get_invoice_periods(contract.end_date,
                    contract.start_date)}
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
            'amount': 0,
            'tax_amount': 0,
            'total_amount': 0,
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
            if config._tax_rounding == 'line':
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
                    'amount': amount,
                    'tax_amount': tax_amount,
                    'total_amount': amount + tax_amount,
                    })
            displayer['amount'] += amount
            displayer['tax_amount'] += tax_amount
            displayer['total_amount'] += amount + tax_amount
    ###########################################################################
    # End calculation cache                                                   #
    ###########################################################################


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
            sort=False, depends=['direct_debit', 'direct_debit_day']),
        'get_direct_debit_day_selector', 'setter_void')
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
    payer = fields.Many2One('party.party', 'Payer',
        states={'invisible': ~Eval('direct_debit'),
            'required': And(Bool(Eval('direct_debit', False)),
                (Eval('_parent_contract', {}).get('status', '') ==
                    'active'))},
        depends=['direct_debit'], ondelete='RESTRICT')

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
        if (self.billing_mode.direct_debit and str(self.direct_debit_day)
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
            month, day = start.month, start.day
            if month == 2 and day == 29:
                # Handle leap year...
                month, day = 3, 1
            rule_start = datetime.datetime.combine(
                datetime.date(start.year - 1, month, day), datetime.time())
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
                new_date = coog_date.add_year(start_date, start.year -
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
            nb_years = coog_date.number_of_years_between(start, end)
            if nb_years:
                occurences = [None] * (nb_years - 1) + [
                    coog_date.add_year(start, nb_years)]
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
                if self.prorate_premiums:
                    ratio = (Decimal((end - last_date).days + 1)
                        / Decimal((next_date - last_date).days))
                    amount += self.amount * ratio
                elif (end - last_date).days + 1 != 0:
                    amount += self.amount
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
                invoice_type='out',
                account=self.account,
                coverage_start=start,
                coverage_end=end,
                details=[InvoiceLineDetail.new_detail_from_premium(self)],
                )]


class ContractInvoice(model.CoogSQL, model.CoogView):
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
        pool = Pool()
        Reconciliation = pool.get('account.move.reconciliation')
        Invoice = pool.get('account.invoice')

        invoices = []
        cancelled_invoices = []
        for contract_invoice in contract_invoices:
            if contract_invoice.invoice.state == 'cancel':
                cancelled_invoices.append(contract_invoice.invoice)
            else:
                invoices.append(contract_invoice.invoice)
        if cancelled_invoices:
            logging.getLogger('contract.invoice').warning('Cancel method '
                'called on already cancelled invoices : %s.' % ', '.join(
                    [x.number for x in cancelled_invoices]))
            traceback.print_stack()

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
            return {
                'up_to_date': coog_date.add_day(contract.last_invoice_end, 1),
                }
        else:
            return {
                'up_to_date': contract.start_date,
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
    __name__ = 'contract.premium.display'

    @classmethod
    def get_children_fields(cls):
        children = super(DisplayContractPremium, cls).get_children_fields()
        children['contract'].append('covered_elements')
        children['contract.covered_element'] = ['options']
        children['options'].append('extra_premiums')
        return children


class ContractSubStatus:
    __name__ = 'contract.sub_status'

    hold_billing = fields.Boolean('Hold Billing', depends=['status'],
        states={'invisible': Eval('status') != 'hold'})
