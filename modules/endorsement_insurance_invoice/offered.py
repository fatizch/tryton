from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, model
from trytond.modules.endorsement import field_mixin


__metaclass__ = PoolMeta
__all__ = [
    'EndorsementDefinition',
    'EndorsementPart',
    'EndorsementBillingInformationField',
    ]


class EndorsementDefinition:
    __name__ = 'endorsement.definition'

    requires_contract_rebill = fields.Function(
        fields.Boolean('Requires Contract Rebill'),
        'get_requires_contract_rebill')

    def get_methods_for_model(self, model_name):
        methods = super(EndorsementDefinition, self).get_methods_for_model(
            model_name)
        if model_name == 'contract' and self.requires_contract_rebill:
            methods += Pool().get('ir.model.method').search([
                    ('xml_id', '=', 'endorsement_insurance_invoice.'
                        'contract_rebill_after_endorsement_method')])
        return methods

    def get_requires_contract_rebill(self, name):
        return any((endorsement_part.requires_contract_rebill
                for endorsement_part in self.endorsement_parts))


class EndorsementPart:
    __name__ = 'endorsement.part'

    billing_information_fields = fields.One2Many(
        'endorsement.contract.billing_information.field', 'endorsement_part',
        'Billing Information Fields', states={
            'invisible': Eval('kind', '') != 'billing_information'},
        depends=['kind'])
    requires_contract_rebill = fields.Boolean('Requires Contract Rebill')

    @classmethod
    def __setup__(cls):
        super(EndorsementPart, cls).__setup__()
        cls.kind.selection.append(
            ('billing_information', 'Billing Information'))

    def on_change_with_endorsed_model(self, name=None):
        if self.kind == 'billing_information':
            return Pool().get('ir.model').search([
                    ('model', '=', 'contract')])[0].id
        return super(EndorsementPart, self).on_change_with_endorsed_model(name)

    def clean_up(self, endorsement):
        super(EndorsementPart, self).clean_up(endorsement)
        if self.billing_information_fields:
            self.clean_up_relation(endorsement, 'billing_information_fields',
                'billing_informations')


class EndorsementBillingInformationField(
        field_mixin('contract.billing_information'), model.CoopSQL,
        model.CoopView):
    'Endorsement Billing Information Field'

    __name__ = 'endorsement.contract.billing_information.field'
