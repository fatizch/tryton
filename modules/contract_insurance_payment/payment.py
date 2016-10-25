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


__metaclass__ = PoolMeta
__all__ = [
    'Payment',
    'Journal',
    'JournalFailureAction',
    ]


class Journal:
    __name__ = 'account.payment.journal'

    failure_billing_mode = fields.Many2One('offered.billing_mode',
        'Failure Billing Mode', ondelete='RESTRICT',
        domain=[('direct_debit', '=', False)],
        depends=['process_method'])

    @classmethod
    def _export_light(cls):
        return super(Journal, cls)._export_light() | {'failure_billing_mode'}


class JournalFailureAction:
    __name__ = 'account.payment.journal.failure_action'

    @classmethod
    def __setup__(cls):
        super(JournalFailureAction, cls).__setup__()
        manual_payment = ('move_to_manual_payment', 'Move to manual payment')
        cls.action.selection.append(manual_payment)


class Payment:
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
        return payment.line.move.origin.contract

    @classmethod
    def fail_move_to_manual_payment(cls, payments):
        pool = Pool()
        ContractBillingInformation = pool.get('contract.billing_information')
        Contract = pool.get('contract')
        Invoice = pool.get('account.invoice')
        Date = pool.get('ir.date')
        invoices = []
        payments = sorted(payments, key=cls._group_per_contract_key)
        for contract, _grouped_payments in groupby(payments,
                key=cls._group_per_contract_key):
            if contract is None or contract.status != 'active':
                continue
            grouped_payments = list(_grouped_payments)
            current_billing_mode = contract.billing_information.billing_mode
            if not current_billing_mode.direct_debit:
                continue
            failure_billing_mode = current_billing_mode.failure_billing_mode \
                if current_billing_mode.failure_billing_mode \
                else grouped_payments[0].journal.failure_billing_mode
            if not failure_billing_mode:
                raise Exception('no failure_billing_mode on journal %s'
                    % (grouped_payments[0].journal.rec_name))

            next_invoice_dates = [payment.line.move.origin.end
                for payment in grouped_payments
                if (payment.line.move.origin and
                    getattr(payment.line.move.origin, 'end', None))]
            if next_invoice_dates:
                next_invoice_date = max(next_invoice_dates)
            else:
                # case when only non periodic invoice payment is failed
                next_invoice_date = max(contract.start_date,
                    contract.last_paid_invoice_end or datetime.date.min)

            new_billing_date = (next_invoice_date + relativedelta(days=1)) if \
                next_invoice_dates else next_invoice_date
            new_billing_information = ContractBillingInformation(
                date=max(Date.today(), new_billing_date),
                billing_mode=failure_billing_mode,
                payment_term=failure_billing_mode.allowed_payment_terms[0])
            contract.billing_informations = contract.billing_informations + \
                (new_billing_information,)
            contract.save()
            Contract.calculate_prices([contract],
                start=new_billing_information.date)

            invoices.extend(Contract.invoice([contract],
                up_to_date=next_invoice_date))
        Invoice.post([contract_invoice.invoice
                for contract_invoice in invoices])

    @classmethod
    def fail_retry(cls, payments):
        super(Payment, cls).fail_retry(payments)
        pool = Pool()
        Invoice = pool.get('account.invoice')
        MoveLine = pool.get('account.move.line')

        payment_line_to_modify = []
        for payment in payments:
            if not isinstance(payment.line.move.origin, Invoice):
                continue
            contract_invoice = payment.line.move.origin.contract_invoice
            invoice = payment.line.move.origin

            if not contract_invoice:
                continue
            with Transaction().set_context(
                    contract_revision_date=contract_invoice.start):
                res = invoice.update_move_line_from_billing_information(
                    payment.line,
                    contract_invoice.contract.billing_information)
                for field_name, field_value in res.iteritems():
                    setattr(payment.line, field_name, field_value)
                payment_line_to_modify += [[payment.line], {
                            'payment_date': payment.line.payment_date
                        }]

        if payment_line_to_modify:
            MoveLine.write(*payment_line_to_modify)
