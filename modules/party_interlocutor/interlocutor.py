# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval

from trytond.modules.coog_core import model, coog_string

__all__ = [
    'ContactInterlocutor',
    'PartyContactInterlocutorPartyContactMechanism',
    ]


class ContactInterlocutor(model.CoogSQL, model.CoogView):
    'Party Interlocutor'

    __name__ = 'party.interlocutor'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    address = fields.Many2One('party.address', 'Address',
        domain=[('party', '=', Eval('party'))],
        ondelete='RESTRICT', depends=['party'])
    contact_mechanisms = fields.Many2Many(
        'party.interlocutor-party.contact_mechanism',
        'interlocutor', 'contact_mechanism', 'Contact Mechanisms',
        domain=[('party', '=', Eval('party'))], depends=['party'])
    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
        domain=[('is_company', '=', True)], required=True, select=True)
    email = fields.Function(
        fields.Char('E-Mail'), 'get_mechanism')
    phone = fields.Function(
        fields.Char('Phone'), 'get_mechanism')
    mobile = fields.Function(
        fields.Char('Mobile'), 'get_mechanism')

    def get_mechanism(self, name):
        for mechanism in self.contact_mechanisms:
            if mechanism.type == name:
                return mechanism.value
        return ''

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        return self.code if self.code else coog_string.slugify(self.name)


class PartyContactInterlocutorPartyContactMechanism(model.CoogSQL,
        model.CoogView):
    'Party Contact Interlocutor Party Contact Mechanism Relation'

    __name__ = 'party.interlocutor-party.contact_mechanism'

    interlocutor = fields.Many2One('party.interlocutor',
        'Contact Interlocutor', ondelete='CASCADE',
        required=True, select=True)
    contact_mechanism = fields.Many2One('party.contact_mechanism',
        'Contact Mechanism', ondelete='RESTRICT', required=True, select=True)
