# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Not, Bool, If

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'ChangeBillingInformation',
    'ChangeDirectDebitAccount',
    ]


class ChangeBillingInformation:
    __name__ = 'contract.billing_information.change'

    mandate_needed = fields.Boolean('Mandate Needed',
        states={'invisible': True})
    sepa_signature_date = fields.Date('Sepa Mandate Signature Date',
        states={
            'required': (Eval('mandate_needed', False) &
                ~Eval('amend_previous_mandate', False)),
            'invisible': Not(Eval('mandate_needed', False) &
                ~Eval('amend_previous_mandate', False)),
            }, depends=['mandate_needed', 'amend_previous_mandate'])
    amend_previous_mandate = fields.Boolean('Amend Previous Mandate',
        states={'invisible': Not(Bool(Eval('previous_mandate', 'False'))),
            }, depends=['mandate_needed'])
    previous_mandate = fields.Many2One('account.payment.sepa.mandate',
        'Previous Mandate', states={'invisible': True})

    @classmethod
    def __setup__(cls):
        super(ChangeBillingInformation, cls).__setup__()
        cls.other_contracts.domain = [If(
                Not(Bool(Eval('amend_previous_mandate'))),
                cls.other_contracts.domain,
                [('to_propagate', 'in', ('bank_account', 'everything'))])]
        cls.other_contracts.depends.append('amend_previous_mandate')
        cls._error_messages.update({
                'new_mandate_creation': 'A new mandate will be created, this '
                'action cannot be cancelled',
                })

    @classmethod
    def default_amend_previous_mandate(cls):
        return False

    @fields.depends('mandate_needed', 'new_billing_information',
        'sepa_signature_date', 'payer')
    def on_change_new_billing_information(self):
        super(ChangeBillingInformation,
            self).on_change_new_billing_information()
        if not self.new_billing_information:
            return
        Mandate = Pool().get('account.payment.sepa.mandate')
        new_info = self.new_billing_information[0]
        previous_info = self.previous_billing_information[0]
        new_account = (new_info.direct_debit_account or
            new_info.direct_debit_account_selector)
        prev_account = (previous_info.direct_debit_account or
            previous_info.direct_debit_account_selector)
        if (not(new_info.direct_debit) or new_account == prev_account
                or not new_account):
            self.mandate_needed = False
            self.amend_previous_mandate = False
            self.previous_mandate = None
            if new_info.direct_debit:
                new_info.sepa_mandate = previous_info.sepa_mandate
            return
        possible_mandates = None
        if new_info.payer and new_account:
            possible_mandates = Mandate.search([
                    ('state', '=', 'validated'),
                    ('party', '=', new_info.payer.id),
                    ('OR', ('start_date', '=', None),
                        ('start_date', '<', self.effective_date)),
                    ('account_number.account', '=', new_account)])
        if possible_mandates:
            self.mandate_needed = False
            self.amend_previous_mandate = False
            self.previous_mandate = None
            new_info.sepa_mandate = possible_mandates[0]
            self.new_billing_information = self.new_billing_information
            return
        self.mandate_needed = True
        if previous_info.payer in new_account.owners:
            possible_mandates = Mandate.search([
                    ('party', '=', previous_info.payer.id),
                    ('account_number.account', '=', prev_account),
                    ('OR', ('start_date', '=', None),
                        ('start_date', '<', self.effective_date))])
            amendments = Mandate.search([('amendment_of', 'in',
                        [x.id for x in possible_mandates])])
            amended = [m.amendment_of for m in amendments]
            possible_mandates = [x for x in possible_mandates if x
                    not in amended]
            if possible_mandates:
                self.amend_previous_mandate = True
                self.previous_mandate = possible_mandates[0]
                for contract in self.other_contracts:
                    contract.to_propagate = 'bank_account'

    @classmethod
    def billing_information_fields(cls):
        return super(ChangeBillingInformation,
            cls).billing_information_fields() + ['sepa_mandate']

    @classmethod
    def direct_debit_account_only_fields(cls):
        return super(ChangeBillingInformation,
            cls).direct_debit_account_only_fields() + ['sepa_mandate']

    def step_default(self, name):
        defaults = super(ChangeBillingInformation, self).step_default(name)
        defaults['sepa_signature_date'] = None
        defaults['mandate_needed'] = False
        return defaults

    def set_account_owner(self):
        super(ChangeBillingInformation, self).set_account_owner()
        pool = Pool()
        Mandate = pool.get('account.payment.sepa.mandate')
        if self.mandate_needed:
            new_info = self.new_billing_information[0]
            account = (new_info.direct_debit_account or
                new_info.direct_debit_account_selector)
            new_mandate = Mandate()
            new_mandate.party = new_info.payer
            new_mandate.account_number = [x
                for x in account.numbers if x.type == 'iban'][0]
            new_mandate.company = self.contract.company
            new_mandate.type = 'recurrent'
            new_mandate.scheme = 'CORE'
            if not self.amend_previous_mandate:
                self.raise_user_warning('new_mandate_creation',
                    'new_mandate_creation', {})
                new_mandate.signature_date = self.sepa_signature_date
                new_mandate.state = 'validated'
            else:
                amendment_mandate = Mandate.search([
                    ('party', '=', new_info.payer.id),
                    ('state', '=', 'draft'),
                    ('account_number.account', '=', new_mandate.account_number),
                    ('identification', '=',
                        self.previous_mandate.identification),
                    ('start_date', '=', self.effective_date)])
                if amendment_mandate:
                    new_info.sepa_mandate = amendment_mandate[0]
                    return
                new_mandate.state = 'draft'
                new_mandate.identification = \
                    self.previous_mandate.identification
                new_mandate.signature_date = \
                    self.previous_mandate.signature_date
                new_mandate.amendment_of = self.previous_mandate
                new_mandate.start_date = self.effective_date
            new_mandate.save()
            new_info.sepa_mandate = new_mandate


class ChangeDirectDebitAccount(ChangeBillingInformation):
    __name__ = 'contract.direct_debit_account.change'

    @classmethod
    def __setup__(cls):
        super(ChangeDirectDebitAccount, cls).__setup__()
        cls.other_contracts.domain = [If(
                Not(Bool(Eval('amend_previous_mandate'))),
                cls.other_contracts.domain,
                [('to_propagate', 'in', ('bank_account',))])]

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(ChangeDirectDebitAccount, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods.add('update_sepa_mandates')
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(ChangeDirectDebitAccount,
            cls).get_draft_methods_for_model(model_name)
        if model_name == 'contract':
            methods.add('update_sepa_mandates')
        return methods
