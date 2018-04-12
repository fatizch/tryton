# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from itertools import groupby
from dateutil.relativedelta import relativedelta

from trytond.tools import grouped_slice
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields
from trytond.modules.account_payment_cog.payment import MergedPaymentsMixin


__all__ = [
    'Payment',
    'Journal',
    'JournalFailureAction',
    'MergedPaymentsByContracts',
    'PaymentCreationStart',
    'PaymentCreation',
    ]


class Journal:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.journal'

    failure_billing_mode = fields.Many2One('offered.billing_mode',
        'Failure Billing Mode', ondelete='RESTRICT',
        domain=[('direct_debit', '=', False)],
        depends=['process_method'])

    @classmethod
    def _export_light(cls):
        return super(Journal, cls)._export_light() | {'failure_billing_mode'}


class JournalFailureAction:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.journal.failure_action'

    @classmethod
    def __setup__(cls):
        super(JournalFailureAction, cls).__setup__()
        manual_payment = ('move_to_manual_payment', 'Move to manual payment')
        cls.action.selection.append(manual_payment)
        cls._fail_actions_order.insert(0, 'move_to_manual_payment')


class Payment:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment'

    contract = fields.Function(
        fields.Many2One('contract', 'Contract'),
        'get_contract', searcher='search_contract')

    @classmethod
    def get_contract(cls, payments, name):
        pool = Pool()
        payment = cls.__table__()
        line = pool.get('account.move.line').__table__()
        cursor = Transaction().connection.cursor()

        result = {x.id: None for x in payments}
        for payments_slice in grouped_slice(payments):
            query = payment.join(line,
                condition=(payment.line == line.id)
                ).select(payment.id, line.contract,
                where=(payment.id.in_([x.id for x in payments_slice])),
                )
            cursor.execute(*query)
            for k, v in cursor.fetchall():
                result[k] = v
        return result

    @classmethod
    def search_contract(cls, name, clause):
        return [('line.contract',) + tuple(clause[1:])]

    def get_reference_object_for_edm(self, template):
        if not self.line.contract:
            return super(Payment, self).get_reference_object_for_edm(template)
        return self.line.contract

    @classmethod
    def _group_per_contract_key(cls, payment):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        if not isinstance(payment.line.move.origin, Invoice):
            return None
        return (payment.line.move.origin.contract,)

    @classmethod
    def fail_move_to_manual_payment(cls, *args):
        pool = Pool()
        Contract = pool.get('contract')
        Invoice = pool.get('account.invoice')
        MoveLine = pool.get('account.move.line')
        contracts_to_save = []
        invoices = []
        lines_to_update = []
        for payments, _ in args:
            payments = sorted(payments, key=cls._group_per_contract_key)
            for contracts, _grouped_payments in groupby(payments,
                    key=cls._group_per_contract_key):
                if not contracts:
                    continue
                for contract in contracts:
                    to_save = cls.move_contract_to_manual_payment(contract,
                        _grouped_payments)
                    if to_save:
                        contracts_to_save.append(to_save)

            if contracts_to_save:
                Contract.save([x[0] for x in contracts_to_save])
            for contract, billing_info_date, next_invoice_date \
                    in contracts_to_save:
                Contract.calculate_prices([contract], start=billing_info_date)
                invoices.extend(Contract.invoice([contract],
                    up_to_date=next_invoice_date))
                for invoice in contract.invoices:
                    if (invoice.invoice_state == 'posted' and invoice.start
                            and invoice.start >= next_invoice_date):
                        lines_to_update += invoice.invoice.lines_to_pay

        if lines_to_update:
            MoveLine.write(lines_to_update, {'payment_date': None})

        Invoice.post([contract_invoice.invoice
                for contract_invoice in invoices])

    @classmethod
    def move_contract_to_manual_payment(cls, contract, payments):
        pool = Pool()
        ContractBillingInformation = pool.get('contract.billing_information')
        Date = pool.get('ir.date')
        today = Date.today()
        if contract is None or contract.status not in ('active', 'terminated',
                'hold'):
            return
        grouped_payments = list(payments)
        current_billing_mode = contract.billing_information.billing_mode
        if not current_billing_mode.direct_debit:
            return
        failure_billing_mode = current_billing_mode.failure_billing_mode \
            if current_billing_mode.failure_billing_mode \
            else grouped_payments[0].journal.failure_billing_mode
        if not failure_billing_mode:
            raise Exception('no failure_billing_mode on journal %s'
                % (grouped_payments[0].journal.rec_name))

        start_dates = [payment.line.move.origin.start
            for payment in grouped_payments
            if getattr(payment.line.move.origin, 'start', None)]
        if start_dates:
            billing_change_date = min(start_dates)
        else:
            # case when only non periodic invoice payment is failed
            billing_change_date = max(contract.initial_start_date,
                contract.last_paid_invoice_end or datetime.date.min)\
                + relativedelta(days=1)

        for billing_info in contract.billing_informations:
            if billing_info.date == billing_change_date or (
                        not billing_info.date
                        and today < contract.initial_start_date):
                billing_info.billing_mode = failure_billing_mode
                billing_info.payment_term = \
                    failure_billing_mode.allowed_payment_terms[0]
                date = billing_info.date
                break
        else:
            new_billing_information = ContractBillingInformation(
                date=billing_change_date,
                billing_mode=failure_billing_mode,
                payment_term=failure_billing_mode.allowed_payment_terms[0])
            contract.billing_informations = contract.billing_informations + \
                (new_billing_information,)
            date = new_billing_information.date

        contract.billing_informations = list(contract.billing_informations)
        return contract, date, billing_change_date

    @classmethod
    def fail_retry(cls, *args):
        super(Payment, cls).fail_retry(*args)
        pool = Pool()
        Invoice = pool.get('account.invoice')
        MoveLine = pool.get('account.move.line')

        to_save = []
        for payments, _ in args:
            for payment in payments:
                if not isinstance(payment.line.move.origin, Invoice):
                    continue
                contract_invoice = payment.line.move.origin.contract_invoice
                invoice = payment.line.move.origin

                if not contract_invoice:
                    continue
                with Transaction().set_context(
                        contract_revision_date=contract_invoice.start):
                    invoice.update_move_line_from_billing_information(
                        payment.line,
                        contract_invoice.contract.billing_information)
                    to_save.append(payment.line)

        if to_save:
            MoveLine.save(to_save)

    @classmethod
    def get_objects_for_fail_prints(cls, report, payments):
        MergedPaymentsByContracts = Pool().get(
            'account.payment.merged.by_contract')
        if report.on_model.model != 'account.payment.merged.by_contract':
            return super(Payment, cls).get_objects_for_fail_prints(report,
                payments)
        merged_ids = list(set(x.merged_id for x in payments))
        contract_ids = list(set(x.contract for x in payments))
        payments = MergedPaymentsByContracts.search([
                ('merged_id', 'in', merged_ids),
                ('contract', 'in', contract_ids)])
        return payments


class MergedPaymentsByContracts(MergedPaymentsMixin):
    'Merged payments by contracts'

    __name__ = 'account.payment.merged.by_contract'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    merged_payment = fields.Function(
        fields.Many2One('account.payment.merged', 'Merged Payment'),
        'get_merged_payment')

    @classmethod
    def get_payments(cls, merged_payments, name):
        tables = cls.get_tables()
        move_line, payment = [tables[x] for x in ['account.move.line',
                'account.payment']]
        cursor = Transaction().connection.cursor()
        res = {(x.merged_id, x.contract.id): [x.id, []]
            for x in merged_payments}
        cursor.execute(*move_line.select(move_line.id, move_line.contract,
                where=move_line.contract.in_([x[1] for x in res.keys()])))
        lines_and_contracts = dict(cursor.fetchall())
        cursor.execute(*payment.select(
                payment.id, payment.merged_id, payment.line,
                where=((payment.merged_id.in_([x[0] for x in res.keys()]) &
                    (payment.line.in_(lines_and_contracts.keys()))))))
        for payment_id, merged_id, line in cursor.fetchall():
            res[(merged_id, lines_and_contracts[line])][1].append(payment_id)
        return {v[0]: v[1] for v in res.values()}

    def get_merged_payment(self, name):
        return Pool().get('account.payment.merged').search([
                ('merged_id', '=', self.merged_id)])[0]

    @classmethod
    def _table_models(cls):
        return super(MergedPaymentsByContracts, cls)._table_models() + \
            ['account.move.line']

    @classmethod
    def get_query_table(cls, tables):
        move_line = tables['account.move.line']
        payment = tables['account.payment']
        base_table = super(MergedPaymentsByContracts, cls).get_query_table(
            tables)
        return base_table.join(move_line,
            condition=move_line.id == payment.line)

    @classmethod
    def get_select_fields(cls, tables):
        select_fields = super(MergedPaymentsByContracts,
            cls).get_select_fields(tables)
        select_fields['contract'] = tables['account.move.line'].contract.as_(
            'contract')
        return select_fields

    @classmethod
    def get_group_by_clause(cls, tables):
        move_line = tables['account.move.line']
        clause = super(MergedPaymentsByContracts, cls).get_group_by_clause(
            tables)
        clause['contract'] = move_line.contract
        return clause


class PaymentCreationStart:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.payment_creation.start'

    @fields.depends('journal', 'possible_journals')
    def on_change_with_lines_to_pay_filter(self, name=None):
        Line = Pool().get('account.move.line')
        ids = super(PaymentCreationStart, self
            ).on_change_with_lines_to_pay_filter(name)
        if not ids or len(self.possible_journals) != 1:
            return ids
        lines = Line.browse(ids)
        return [x.id for x in lines if x.contract
            and x.contract.product.payment_journal == self.journal]


class PaymentCreation:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.creation'

    @classmethod
    def get_possible_journals(cls, lines, kind=None):
        '''
        Here, we return only one possible journal (Journal mix is not allowed
        because the related product defines the payment journal to use)
        '''
        Line = Pool().get('account.move.line')
        payment_journals = Line.get_configuration_journals_from_lines(lines)
        if payment_journals:
            return [payment_journals[0]] if payment_journals else []
        return super(PaymentCreation, cls).get_possible_journals(lines, kind)

    def default_start(self, values):
        Line = Pool().get('account.move.line')
        lines = self.get_move_lines_from_active_model()
        payment_journals = Line.get_configuration_journals_from_lines(lines)
        defaults = super(PaymentCreation, self).default_start(values)
        if payment_journals:
            defaults['journal'] = payment_journals[0].id \
                if payment_journals[0] else None
        return defaults
