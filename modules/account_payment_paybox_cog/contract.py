# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby

from trytond.pool import PoolMeta, Pool

__all__ = [
    'Contract',
    ]


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._error_messages.update({
                'invalid_nb_invoices': 'Invoices number should be positive',
                'invalid_nb_lines_to_pay': 'Lines to pay number should be '
                'strictily positive',
                })

    def pay_with_paybox(self, nb_invoices=0, nb_lines_to_pay=1):
        if not self.billing_information.process_method != 'paybox':
            return
        if nb_invoices < 0:
            self.append_functional_error('invalid_nb_invoices')
        if nb_lines_to_pay < 1:
            self.append_functional_error('invalid_nb_lines_to_pay')
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Payment = pool.get('account.payment')
        PaymentGroup = pool.get('account.payment.group')
        PaymentProcess = pool.get('account.payment.process')
        Group = Pool().get('account.payment.group')
        contract_invoices = sorted([ci.invoice
                for ci in self.invoices
                if ci.invoice.state == 'posted'],
            key=lambda x: x.invoice_date)
        invoices_to_pay = contract_invoices
        if nb_invoices > 0:
            invoices_to_pay = contract_invoices[0:nb_invoices]
        invoices_lines_to_pay = sorted([l
                for invoice in invoices_to_pay
                for l in invoice.lines_to_pay],
            key=lambda x: x.maturity_date)
        lines_to_pay = [l for l in invoices_lines_to_pay[0:nb_lines_to_pay]
            if not l.reconciliation]
        created_payments = MoveLine.create_payments(lines_to_pay)
        if not created_payments:
            return
        payment_groups = []
        payments_key = PaymentProcess._group_payment_key
        paybox_payments = [p for p in created_payments
            if p.journal_method == 'paybox']
        payments = sorted(paybox_payments, key=payments_key)
        for key, grouped_payments in groupby(payments, key=payments_key):
            def create_payment_group():
                payment_group = Group(**(dict((k, v) for k, v in key)))
                payment_group.save()
                payment_groups.append(payment_group)
                return payment_group
            Payment.process(list(grouped_payments), create_payment_group)
        groups_to_save = []
        for payment_group in payment_groups:
            payment_group.generate_paybox_url()
            groups_to_save.append(payment_group)
        if groups_to_save:
            PaymentGroup.save(groups_to_save)
