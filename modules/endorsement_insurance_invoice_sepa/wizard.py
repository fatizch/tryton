from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Not

from trytond.modules.cog_utils import fields

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
            'required': Eval('mandate_needed', False),
            'invisible': Not(Eval('mandate_needed', False)),
            }, depends=['mandate_needed'])

    @classmethod
    def __setup__(cls):
        super(ChangeBillingInformation, cls).__setup__()
        cls._error_messages.update({
                'new_mandate_creation': 'A new mandate will be created, this '
                'action cannot be cancelled',
                })

    @fields.depends('mandate_needed', 'new_billing_information',
        'sepa_signature_date', 'subscriber')
    def on_change_new_billing_information(self):
        super(ChangeBillingInformation,
            self).on_change_new_billing_information()
        Mandate = Pool().get('account.payment.sepa.mandate')
        new_info = self.new_billing_information[0]
        if not(new_info.direct_debit and (new_info.direct_debit_account
                    or new_info.direct_debit_account_selector)):
            self.mandate_needed = False
            return
        possible_mandates = Mandate.search([
                ('party', '=', self.subscriber.id),
                ('account_number.account', '=',
                    (new_info.direct_debit_account or
                        new_info.direct_debit_account_selector).id)])
        if possible_mandates:
            self.mandate_needed = False
            self.new_billing_information[0].sepa_mandate = possible_mandates[0]
            self.new_billing_information = self.new_billing_information
            return
        self.mandate_needed = True

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

    def set_subscriber_as_account_owner(self):
        super(ChangeBillingInformation, self).set_subscriber_as_account_owner()
        pool = Pool()
        Mandate = pool.get('account.payment.sepa.mandate')
        if self.mandate_needed:
            new_info = self.new_billing_information[0]
            account = (new_info.direct_debit_account or
                new_info.direct_debit_account_selector)
            self.raise_user_warning('new_mandate_creation',
                'new_mandate_creation', {})
            new_mandate = Mandate()
            new_mandate.party = self.subscriber
            new_mandate.account_number = [x
                for x in account.numbers if x.type == 'iban'][0]
            new_mandate.signature_date = self.sepa_signature_date
            new_mandate.company = self.contract.company
            new_mandate.state = 'validated'
            new_mandate.type = 'recurrent'
            new_mandate.scheme = 'CORE'
            new_mandate.save()
            new_info.sepa_mandate = new_mandate


class ChangeDirectDebitAccount(ChangeBillingInformation):
    __name__ = 'contract.direct_debit_account.change'

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
