# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, And, Bool
from trytond.transaction import Transaction
from trytond.model import dualmethod

from trytond.modules.coog_core import model, fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractBillingInformation',
    ]


class Contract:
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'init_sepa_mandate': {},
                })

    @dualmethod
    @model.CoogView.button
    def init_sepa_mandate(cls, contracts):
        # Force refresh of link as contract version could be outdated
        for contract in contracts:
            contract.billing_information.contract = contract
            contract.billing_information.init_sepa_mandate()

    def after_activate(self):
        super(Contract, self).after_activate()
        self.init_sepa_mandate()

    @classmethod
    def update_contract_after_import(cls, contracts):
        super(Contract, cls).update_contract_after_import(contracts)
        for contract in contracts:
            contract.init_sepa_mandate()

    @classmethod
    def update_mandates_from_date(cls, contracts, date):
        # Update sepa mandate on already generated invoices from a given start
        # date. The basic idea is to modify existing validated or posted
        # invoices for which there is a planned payment after the date.
        Invoice = Pool().get('account.invoice')
        update_data = {contract.id: utils.get_value_at_date(
                contract.billing_informations, date).sepa_mandate
            for contract in contracts}
        clause = ['OR'] + [
            [('contract', '=', contract), ('state', '=', 'posted'),
                ('party', '=', mandate.party)]
            for contract, mandate in update_data.items()]

        invoices = Invoice.search(clause)
        to_save = []
        for invoice in invoices:
            if not invoice.sepa_mandate:
                continue
            if invoice.state == 'posted' and max(
                    [x.payment_date or x.maturity_date for x in
                        invoice.lines_to_pay] or [datetime.date.min]) < date:
                continue
            invoice.sepa_mandate = update_data[invoice.contract.id]
            to_save.append(invoice)
        if to_save:
            Invoice.save(to_save)

    def action_required_when_payments_failed(self):
        # when contract is void without due amount no need to process any
        # action following a payment failed
        return self.status != 'void' or self.balance > 0

    def init_billing_information(self):
        super(Contract, self).init_billing_information()
        if self.subscriber and self.billing_informations:
            self.billing_informations[0].payer = self.subscriber


class ContractBillingInformation:
    __name__ = 'contract.billing_information'

    sepa_mandate = fields.Many2One('account.payment.sepa.mandate',
        'Sepa Mandate', states={
            'invisible': ~Eval('direct_debit'),
            'required': And(Eval('direct_debit', False),
                (Eval('_parent_contract', {}).get('status', '') == 'active')),
            'readonly': Bool(Eval('contract_status')) & (
                    Eval('contract_status') != 'quote'),

            }, domain=[
            ('account_number.account', '=', Eval('direct_debit_account'))],
        depends=['direct_debit', 'direct_debit_account', 'contract_status'],
        ondelete='RESTRICT')

    @classmethod
    def _export_light(cls):
        return (super(ContractBillingInformation, cls)._export_light() |
            set(['sepa_mandate']))

    def new_mandate(self, type_, scheme, state):
        Mandate = Pool().get('account.payment.sepa.mandate')
        return Mandate(
            party=self.contract.payer,
            account_number=self.direct_debit_account.numbers[0],
            type=type_,
            scheme=scheme,
            signature_date=(self.contract.signature_date or
                self.contract.start_date),
            company=self.contract.company,
            state=state)

    def unicity_key_for_mandate(self, numbers_id):
        return [
            ('type', '=', 'recurrent'),
            ('scheme', '=', 'CORE'),
            ('account_number', 'in', numbers_id),
            ('party', '=', self.contract.payer.id),
            ]

    def init_sepa_mandate(self):
        pool = Pool()
        Mandate = pool.get('account.payment.sepa.mandate')
        if (not self.direct_debit or self.sepa_mandate or
                not self.direct_debit_account):
            return
        mandates = Mandate.search(self.unicity_key_for_mandate([number.id
                    for number in self.direct_debit_account.numbers]))
        for mandate in mandates:
            self.sepa_mandate = mandate
            self.save()
            return
        self.sepa_mandate = self.new_mandate('recurrent', 'CORE', 'validated')
        self.save()

    @classmethod
    def copy(cls, instances, default=None):
        default = {} if default is None else default.copy()
        if Transaction().context.get('copy_mode', '') == 'functional':
            skips = cls._export_skips() | cls.functional_skips_for_duplicate()
            for x in skips:
                default.setdefault(x, None)
        return super(ContractBillingInformation, cls).copy(instances,
            default=default)

    @classmethod
    def functional_skips_for_duplicate(cls):
        return set(['sepa_mandate'])

    @fields.depends('direct_debit_account', 'sepa_mandate')
    def on_change_billing_mode(self):
        previous_account = self.direct_debit_account
        super(ContractBillingInformation, self).on_change_billing_mode()
        if previous_account != self.direct_debit_account:
            self.sepa_mandate = None

    @fields.depends('direct_debit_account', 'sepa_mandate')
    def on_change_direct_debit_account(self):
        if not self.direct_debit_account:
            self.sepa_mandate = None

    @fields.depends('contract', 'payer', 'sepa_mandate', 'date',
        'direct_debit_account')
    def on_change_payer(self):
        Mandate = Pool().get('account.payment.sepa.mandate')
        super(ContractBillingInformation, self).on_change_payer()
        self.sepa_mandate = None
        if self.direct_debit_account and self.payer and self.contract \
                and self.direct_debit_account:
            possible_mandates = Mandate.search([
                    ('party', '=', self.payer.id),
                    ('account_number.account', '=',
                        self.direct_debit_account.id),
                    ('signature_date', '>=', self.date
                        or self.contract.start_date)
                    ])
            if possible_mandates:
                self.sepa_mandate = possible_mandates[0]
