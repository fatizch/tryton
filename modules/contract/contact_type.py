from trytond.modules.cog_utils import model, fields, coop_string, utils
from trytond.pyson import Eval, Bool

__all__ = [
    'ContactType',
    'ContractContact',
    ]


class ContactType(model.CoopSQL, model.CoopView):
    'Contact Type'

    __name__ = 'contract.contact.type'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)


class ContractContact(model.CoopSQL, model.CoopView):
    'Contract Contact'

    __name__ = 'contract.contact'

    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE',
        required=True, select=True)
    type = fields.Many2One('contract.contact.type', 'Type',
        ondelete='RESTRICT', required=True)
    party = fields.Many2One('party.party', 'Party', ondelete='RESTRICT',
        required=True)
    address = fields.Many2One('party.address', 'Address', ondelete='RESTRICT',
        domain=[('party', '=', Eval('party'))],
        depends=['party', 'is_address_required'],
        states={'required': Bool(Eval('is_address_required'))})
    is_address_required = fields.Function(
        fields.Boolean('Is Address Required', depends=['type']),
        'on_change_with_is_address_required')

    def get_default_address_from_party(self):
        instances = utils.get_domain_instances(self, 'address')
        if len(instances) >= 1:
            return instances[0]

    @fields.depends('party')
    def on_change_with_address(self):
        if not self.party or not self.address:
            address = self.get_default_address_from_party()
            if address:
                return address.id

    @fields.depends('type')
    def on_change_with_is_address_required(self, name=None):
        if self.type:
            return self.type.code in ('subscriber', 'accepting_beneficiary')
        return False
