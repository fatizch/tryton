# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby

from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.model import Workflow
from trytond.model.exceptions import ValidationError

from trytond.modules.coog_core import fields, utils, coog_string, model
from trytond.modules.account_payment_sepa_cog.payment import \
    MergedBySepaPartyMixin

__all__ = [
    'Mandate',
    'Payment',
    'PaymentCreationStart',
    'Journal',
    'JournalFailureAction',
    'MergedPaymentsByContracts',
    ]


class Payment(metaclass=PoolMeta):
    __name__ = 'account.payment'

    @fields.depends('contract', 'date')
    def on_change_with_payer(self, name=None):
        return super(Payment, self).on_change_with_payer(name)

    def init_payer(self):
        if self.contract:
            with Transaction().set_context(
                    contract_revision_date=self.date):
                payer = self.contract.payer
                if payer and (not self.bank_account or
                        payer in self.bank_account.owners):
                    return payer.id
        return super(Payment, self).init_payer()

    @fields.depends('line', 'date', 'sepa_mandate', 'bank_account', 'payer',
        'party', 'kind')
    def on_change_line(self):
        super(Payment, self).on_change_line()
        self.sepa_mandate = None
        self.contract = None
        self.bank_account = None
        self.payer = None
        if self.line:
            contract = self.line.contract
            if contract:
                self.contract = contract
                with Transaction().set_context(
                        contract_revision_date=self.date):
                    mandate = contract.billing_information.sepa_mandate
                self.sepa_mandate = mandate
                if mandate:
                    self.bank_account = mandate.account_number.account
        self.payer = self.on_change_with_payer()
        if not self.bank_account and self.kind == 'payable':
            self.bank_account = self.payer.get_bank_account(self.date)

    @classmethod
    def avoid_reject_fee_creation(cls, reject_fee, journal, payments):
        if (not reject_fee or not reject_fee.amount or
                not journal.process_actions_when_payments_failed(payments)):
            return True
        return False

    @classmethod
    def fail_create_reject_fee(cls, *args):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ContractInvoice = pool.get('contract.invoice')
        Configuration = pool.get('account.configuration')
        MoveLine = pool.get('account.move.line')
        config = Configuration(1)

        invoices_to_create = []
        contract_invoices_to_create = []
        payment_date_to_update = []
        for payments, other_args in args:
            reject_fee, *others_args = other_args
            payments_keys = [(x._get_transaction_key(), x) for x in payments]
            payments_keys = sorted(payments_keys, key=lambda x: x[0])
            for key, payments_by_key in groupby(payments_keys,
                    key=lambda x: x[0]):
                payments_list = [payment[1] for payment in payments_by_key]
                payment = payments_list[0]
                sepa_mandate = None
                payment_date = None
                journal = key[1]
                # reject_fee = cls.get_reject_fee(payments_list)
                if cls.avoid_reject_fee_creation(reject_fee, journal,
                        payments_list):
                    continue
                if 'retry' in [action[0] for action in
                        journal.get_fail_actions(payments_list)]:
                    sepa_mandate = payment.sepa_mandate
                    payment_date = \
                        payment.journal.get_next_possible_payment_date(
                            payment.line, payment.date.day)

                if 'present_again_after' in [action[0] for action in
                        journal.get_fail_actions(payments_list)]:
                    # If the action is to present again the payment after the
                    # payment failure, we need to find out in args the journal
                    # failure action to set the next payment day on the line's
                    # payment date.
                    present_again_day = None
                    for other_arg in others_args:
                        if getattr(other_arg, '__name__', None) == \
                                'account.payment.journal.failure_action':
                            present_again_day = int(
                                other_arg.present_again_day or '0')
                    sepa_mandate = payment.sepa_mandate
                    initial_date = payment.line.payment_date or payment.date
                    # Set the new payment_date day on the line
                    if present_again_day and initial_date:
                        new_date = journal.get_next_possible_payment_date(
                            payment.line, present_again_day)
                        new_payment_date = \
                            payment.journal.get_next_possible_payment_date(
                                payment.line, payment.date.day)
                        new_date = min(new_date, new_payment_date)
                        payment_date = new_date
                    else:
                        payment_date = \
                            payment.journal.get_next_possible_payment_date(
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
            for line in i.lines_to_pay:
                lines_to_write += [list(i.lines_to_pay), p]
                break
        if lines_to_write:
            MoveLine.write(*lines_to_write)

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


class Journal(metaclass=PoolMeta):
    __name__ = 'account.payment.journal'

    def process_actions_when_payments_failed(self, payments):
        # no need to process action for contracts that are void without due
        # amount
        return super(Journal, self).process_actions_when_payments_failed(
            payments) and any([(not p.line.contract or
                    p.line.contract.action_required_when_payments_failed())
                for p in payments if p.line])

    @fields.depends('process_method')
    def on_change_process_method(self):
        super(Journal, self).on_change_process_method()
        if self.process_method == 'sepa':
            self.apply_payment_suspension = True


class JournalFailureAction(metaclass=PoolMeta):
    __name__ = 'account.payment.journal.failure_action'

    @classmethod
    def __setup__(cls):
        super(JournalFailureAction, cls).__setup__()
        cls._fail_actions_order.insert(
            cls._fail_actions_order.index('retry') + 1, 'create_reject_fee')

    def get_actions_for_matching_reject_number(self, **kwargs):
        actions = super(JournalFailureAction,
            self).get_actions_for_matching_reject_number(**kwargs)
        if self.rejected_payment_fee:
            actions.append(('create_reject_fee', self.rejected_payment_fee,
                    self))
        return actions


class MergedPaymentsByContracts(MergedBySepaPartyMixin):
    __name__ = 'account.payment.merged.by_contract'


class Mandate(metaclass=PoolMeta):
    __name__ = 'account.payment.sepa.mandate'

    @classmethod
    @model.CoogView.button
    @Workflow.transition('approved')
    def cancel(cls, mandates):
        BillingInfo = Pool().get('contract.billing_information')
        # Get all the billing informations using the sepa mandate in the future
        # or which is currently used.
        billing_informations = BillingInfo.search([
                ('sepa_mandate', 'in', [x.id for x in mandates]),
                ])
        billings_using_sepa_mandate = []
        for billing_information in billing_informations:
            if billing_information.contract.billing_information.sepa_mandate \
                    in mandates:
                billings_using_sepa_mandate.append(billing_information)
            elif billing_information.date and \
                    billing_information.date >= utils.today():
                billings_using_sepa_mandate.append(billing_information)
        with model.error_manager():
            for billing in billings_using_sepa_mandate:
                cls.append_functional_error(
                    ValidationError(gettext(
                            'account_payment_sepa_contract'
                            '.msg_billing_information_with_mandate',
                            contract=billing.contract.contract_number,
                            billing_info=billing.rec_name,
                            date=coog_string.translate_value(billing, 'date'))))
        super(Mandate, cls).cancel(mandates)

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


class PaymentCreationStart(metaclass=PoolMeta):
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
                if mandate and (mandate.signature_date <= self.payment_date or
                        self.kind == 'payable'):
                    payers.append(mandate.party.id)
        return list(set(payers)) or default_payers
