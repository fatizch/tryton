from trytond.modules.cog_utils import model, fields, coop_string
from trytond.pyson import Eval

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
        return coop_string.remove_blank_and_invalid_char(self.name)


class ContractContact(model.CoopSQL, model.CoopView):
    'Contract Contact'

    __name__ = 'contract.contact'

    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE')
    type = fields.Many2One('contract.contact.type', 'Type',
        ondelete='RESTRICT', required=True)
    party = fields.Many2One('party.party', 'Party', ondelete='RESTRICT',
        required=True)
    address = fields.Many2One('party.address', 'Address', ondelete='RESTRICT',
        domain=[('party', '=', Eval('party'))], depends=['party'])
