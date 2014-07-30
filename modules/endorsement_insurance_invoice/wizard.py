from trytond.pool import PoolMeta
from trytond.wizard import StateView, StateTransition, Button
from trytond.pyson import Eval

from trytond.modules.cog_utils import model, fields
from trytond.modules.endorsement import \
    EndorsementWizardStepVersionedObjectMixin

__metaclass__ = PoolMeta
__all__ = [
    'PreviewChanges',
    'ChangeBillingInformation',
    'StartEndorsement',
    ]


class PreviewChanges:
    __name__ = 'endorsement.start.preview_changes'

    previous_total_invoice_amount = fields.Numeric(
        'Previous total invoice amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    new_total_invoice_amount = fields.Numeric('New total invoice amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    currency_symbol = fields.Char('Currency Symbol')
    currency_digits = fields.Integer('Currency Digits')

    @classmethod
    def get_default_values_from_changes(cls, changes):
        result = super(PreviewChanges, cls).get_default_values_from_changes(
            changes)
        # TODO : manage multi_contract
        changes_old = changes['old'].values()[0]
        changes_new = changes['new'].values()[0]
        result['previous_total_invoice_amount'] = changes_old[
            'total_invoice_amount']
        result['new_total_invoice_amount'] = changes_new[
            'total_invoice_amount']
        result['currency_digits'] = changes_new['currency_digits']
        result['currency_symbol'] = changes_new['currency_symbol']
        return result


class ChangeBillingInformation(EndorsementWizardStepVersionedObjectMixin,
        model.CoopView):
    'Change Billing Information'

    __name__ = 'contract.billing_information.change'
    _target_model = 'contract.billing_information'

    contract = fields.Many2One('contract', 'Contract', states={
            'readonly': True})
    product = fields.Many2One('offered.product', 'Product', states={
            'invisible': True})
    subscriber = fields.Many2One('party.party', 'Subscriber', states={
            'invisible': True})

    @classmethod
    def __setup__(cls):
        super(ChangeBillingInformation, cls).__setup__()
        cls.new_value.domain = [
            ('billing_mode.products', '=', Eval('product')),
            ('direct_debit_account.owners', '=', Eval('subscriber'))]
        cls.new_value.depends = ['product', 'subscriber']

    def update_endorsement(self, endorsement, wizard):
        wizard.update_revision_endorsement(self, endorsement,
            'billing_informations')


class StartEndorsement:
    __name__ = 'endorsement.start'

    change_billing_information = StateView(
        'contract.billing_information.change',
        'endorsement_insurance_invoice.change_billing_information_view_form',
        [Button('Previous', 'billing_information_previous',
                'tryton-go-previous'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Next', 'billing_information_next', 'tryton-go-next',
                default=True)])
    billing_information_next = StateTransition()
    billing_information_previous = StateTransition()

    def default_change_billing_information(self, name):
        result = self.get_revision_state_defaults(
            'change_billing_information', 'contract.billing_information',
            'billing_informations',
            'contract_insurance_invoice.'
            'contract_billing_information_view_form')
        endorsement_part = self.get_endorsement_part_for_state(
            'change_billing_information')
        contract = self.get_endorsed_object(endorsement_part)
        result['product'] = contract.product.id
        result['subscriber'] = contract.subscriber.id
        result['contract'] = self.get_endorsed_object(endorsement_part).id
        return result

    def transition_billing_information_next(self):
        self.end_current_part('change_billing_information')
        return self.get_next_state('change_billing_information')

    def transition_billing_information_previous(self):
        self.end_current_part('change_billing_information')
        return self.get_state_before('change_billing_information')
