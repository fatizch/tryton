# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby

from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import fields
from trytond.transaction import Transaction


__metaclass__ = PoolMeta
__all__ = [
    'Mandate',
    'Payment',
    'PaymentCreationStart',
    ]


class Payment:
    __name__ = 'account.payment'

    @fields.depends('contract', 'payment_date', 'sepa_mandate')
    def on_change_with_payer(self, name=None):
        payer = super(Payment, self).on_change_with_payer(name)
        if not payer and self.contract:
            with Transaction().set_context(
                    contract_revision_date=self.date):
                payer = self.contract.payer.id
        return payer

    @fields.depends('line', 'date', 'sepa_mandate', 'bank_account', 'payer',
        'amount')
    def on_change_line(self, name=None):
        super(Payment, self).on_change_line()
        self.sepa_mandate = None
        self.bank_account = None
        if self.line:
            contract = self.line.contract
            if contract:
                self.contract = contract
                with Transaction().set_context(
                        contract_revision_date=self.date):
                    mandate = contract.billing_information.sepa_mandate
                self.sepa_mandate = mandate
                self.bank_account = self.sepa_mandate.account_number.account
        self.payer = self.on_change_with_payer()

    @classmethod
    def fail(cls, payments):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ContractInvoice = pool.get('contract.invoice')
        Configuration = pool.get('account.configuration')
        MoveLine = pool.get('account.move.line')
        config = Configuration(1)

        invoices_to_create = []
        contract_invoices_to_create = []
        payment_date_to_update = []
        payments_keys = [(x._get_transaction_key(), x) for x in payments]
        payments_keys = sorted(payments_keys, key=lambda x: x[0])
        for key, payments_by_key in groupby(payments_keys, key=lambda x: x[0]):
            payments_list = [payment[1] for payment in payments_by_key]
            payment = payments_list[0]
            sepa_mandate = None
            payment_date = None
            reject_fee = cls.get_reject_fee(payments_list)
            if not reject_fee or not reject_fee.amount:
                continue
            if 'retry' in [action[0] for action in
                    key[1].get_fail_actions(payments_list)]:
                sepa_mandate = payment.sepa_mandate
                payment_date = payment.journal.get_next_possible_payment_date(
                        payment.line, payment.date.day)
            journal = config.reject_fee_journal
            account = reject_fee.product.template.account_revenue_used
            name_for_billing = reject_fee.name
            invoice = payment.create_fee_invoice(
                reject_fee.amount, journal, account, name_for_billing,
                sepa_mandate)
            contract = cls.get_contract_for_reject_invoice(payments_list)
            if contract is not None:
                contract_invoice = ContractInvoice(
                    contract=contract, invoice=invoice, non_periodic=True)
                contract_invoices_to_create.append(contract_invoice)
            invoices_to_create.append(invoice)
            payment_date_to_update.append({'payment_date': payment_date})

        Invoice.save(invoices_to_create)
        ContractInvoice.save(contract_invoices_to_create)
        Invoice.post(invoices_to_create)
        lines_to_write = []
        for i, p in zip(invoices_to_create, payment_date_to_update):
            lines_to_write += [list(i.lines_to_pay), p]
        if lines_to_write:
            MoveLine.write(*lines_to_write)

        super(Payment, cls).fail(payments)

    @classmethod
    def get_contract_for_reject_invoice(cls, payments):
        # Contract to attach invoice fee
        contract = None
        for payment in payments:
            if not payment.line.contract or \
                    payment.line.contract.status == 'void':
                # Void contracts cannot be invoiced anyway
                continue
            if not contract:
                contract = payment.line.contract
                continue
            if contract == payment.line.contract:
                continue
            return None
        return contract


class Mandate:
    __name__ = 'account.payment.sepa.mandate'

    def objects_using_me_for_party(self, party=None):
        objects = super(Mandate, self).objects_using_me_for_party(party)
        if objects:
            return objects
        pool = Pool()
        BillingInformation = pool.get('contract.billing_information')
        Invoice = pool.get('account.invoice')
        domain = [('sepa_mandate', '=', self)]
        if party:
            domain.append(('payer', '=', party))
        objects = BillingInformation.search(domain)
        if objects:
            return objects
        domain = [('sepa_mandate', '=', self)]
        if party:
            domain.append(('party', '=', party))
        return Invoice.search(domain)


class PaymentCreationStart:
    __name__ = 'account.payment.payment_creation.start'

    def update_available_payers(self):
        default_payers = super(PaymentCreationStart,
            self).update_available_payers()
        if not self.party or not self.payment_date:
            return
        payers = []
        for contract in self.party.contracts:
            for bill_info in contract.billing_informations:
                mandate = bill_info.sepa_mandate
                if mandate and mandate.signature_date <= self.payment_date:
                    payers.append(mandate.party.id)
        return list(set(payers)) or default_payers
