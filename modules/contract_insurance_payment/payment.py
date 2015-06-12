# -*- coding:utf-8 -*-
from itertools import groupby
from dateutil.relativedelta import relativedelta

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields


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


class JournalFailureAction:
    __name__ = 'account.payment.journal.failure_action'

    @classmethod
    def __setup__(cls):
        super(JournalFailureAction, cls).__setup__()
        manual_payment = ('move_to_manual_payment', 'Move to manual payment')
        cls.action.selection.append(manual_payment)


class Payment:
    __name__ = 'account.payment'

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
            if contract is None:
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

            next_invoice_date = max(payment.line.move.origin.end
                for payment in grouped_payments
                if (payment.line.move.origin and
                    getattr(payment.line.move.origin, 'end', None))
            next_invoice_date += relativedelta(days=1)

            new_billing_information = ContractBillingInformation(
                date=max(Date.today(), next_invoice_date),
                billing_mode=failure_billing_mode,
                payment_term=failure_billing_mode.allowed_payment_terms[0])
            contract.billing_informations = contract.billing_informations + \
                (new_billing_information,)
            contract.save()

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
