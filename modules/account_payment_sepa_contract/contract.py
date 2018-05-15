# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, And, Bool
from trytond.transaction import Transaction
from trytond.model import dualmethod

from trytond.modules.coog_core import model, fields

__all__ = [
    'Contract',
    'ContractBillingInformation',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'init_sepa_mandate': {},
                })

    @fields.depends('subscriber')
    def on_change_product(self):
        super(Contract, self).on_change_product()

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

    def action_required_when_payments_failed(self):
        # when contract is void without due amount no need to process any
        # action following a payment failed
        return self.status != 'void' or self.balance > 0

    def init_billing_information(self):
        super(Contract, self).init_billing_information()
        if getattr(self, 'subscriber', None) and self.billing_informations:
            self.billing_informations[0].payer = self.subscriber

    @fields.depends('billing_informations')
    def on_change_subscriber(self):
        super(Contract, self).on_change_subscriber()
        if not self.billing_informations:
            return
        new_billing_information = self.billing_informations[-1]
        new_billing_information.sepa_mandate = None
        if new_billing_information.payer and \
                new_billing_information.direct_debit_account:
            Mandate = Pool().get('account.payment.sepa.mandate')
            possible_mandates = Mandate.search([
                    ('party', '=', new_billing_information.payer.id),
                    ('account_number.account', '=',
                        new_billing_information.direct_debit_account.id),
                    ('signature_date', '>=', self.start_date)
                    ])
            if possible_mandates:
                new_billing_information.sepa_mandate = possible_mandates[0]
            else:
                new_billing_information.direct_debit_account = None
        else:
            new_billing_information.direct_debit_account = None
        self.billing_informations = [new_billing_information]


class ContractBillingInformation:
    __metaclass__ = PoolMeta
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

    # this method is overload in the specific code for santiane
    @classmethod
    def update_mandate_from_contract(cls, mandate, contract):
        pass

    @classmethod
    def _export_light(cls):
        return (super(ContractBillingInformation, cls)._export_light() |
            set(['sepa_mandate']))

    def new_mandate(self, type_, scheme, state):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Mandate = pool.get('account.payment.sepa.mandate')
        identification = None  # will be set at creation if None below
        product_mandate_sequence = self.contract.product.sepa_mandate_sequence
        if product_mandate_sequence:
            identification = Sequence.get_id(product_mandate_sequence.id)
        mandate = Mandate(
            party=self.contract.payer,
            account_number=self.direct_debit_account.numbers[0],
            type=type_,
            scheme=scheme,
            identification=identification,
            signature_date=(self.contract.signature_date or
                self.contract.start_date),
            company=self.contract.company,
            state=state)
        self.update_mandate_from_contract(mandate, self.contract)
        return mandate

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
