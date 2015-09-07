from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import fields, model
from trytond.modules.endorsement import field_mixin


__metaclass__ = PoolMeta
__all__ = [
    'EndorsementDefinition',
    'EndorsementPart',
    'EndorsementPartyField',
    'EndorsementAddressField',
    'EndorsementRelationField',
    ]


class EndorsementDefinition:
    __name__ = 'endorsement.definition'

    is_party = fields.Function(
        fields.Boolean('Is Party'),
        'get_is_party', searcher='search_is_party')
    generate_contract_endorsements = fields.Function(
        fields.Boolean('Generate Contract Endorsements',
            states={'invisible': ~Bool(Eval('is_party'))},
            depends=['is_party']),
        'on_change_with_generate_contract_endorsements',
        )
    definition_for_contracts = fields.Many2One('endorsement.definition',
        'Endorsement Definition For Contracts',
        states={
            'required': Bool(Eval('generate_contract_endorsements')),
            'invisible': ~Bool(Eval('generate_contract_endorsements')),
            },
        depends=['generate_contract_endorsements'],
        ondelete='RESTRICT',
        domain=[('is_party', '=', False)])

    def get_is_party(self, name):
        return any([x.is_party for x in self.endorsement_parts])

    @fields.depends('ordered_endorsement_parts')
    def on_change_with_generate_contract_endorsements(self, name=None):
        ordered_parts = self.ordered_endorsement_parts
        parts = []
        for ordered in ordered_parts:
            if ordered.endorsement_part:
                parts.append(ordered.endorsement_part)
        return any([x.generate_contract_endorsements is True
                for x in parts])

    @classmethod
    def search_is_party(cls, name, clause):
        return [('ordered_endorsement_parts.endorsement_part.is_party',) +
            tuple(clause[1:])]


class EndorsementPart:
    __name__ = 'endorsement.part'

    is_party = fields.Function(
        fields.Boolean('Is Party', states={'invisible': True}),
        'get_is_party', searcher='search_is_party')
    party_fields = fields.One2Many(
        'endorsement.party.field', 'endorsement_part', 'Party Fields', states={
            'invisible': Eval('kind', '') != 'party'},
        depends=['kind'], delete_missing=True)
    generate_contract_endorsements = fields.Boolean(
        'Generate Contract Endorsements',
        states={'invisible': Eval('kind') != 'party'},
        depends=['kind'])

    @classmethod
    def __setup__(cls):
        super(EndorsementPart, cls).__setup__()
        cls.kind.selection.append(('party', 'Party'))

    @classmethod
    def default_generate_contract_endorsements(cls):
        return False

    def on_change_with_endorsed_model(self, name=None):
        if self.kind == 'party':
            return Pool().get('ir.model').search([
                    ('model', '=', 'party.party')])[0].id
        return super(EndorsementPart, self).on_change_with_endorsed_model(name)

    def get_is_party(self, name):
        return self.kind == 'party'

    @classmethod
    def search_is_party(cls, name, clause):
        if clause[2] is True:
            return [('kind', '=', 'party')]
        else:
            return [('kind', '!=', 'party')]


class EndorsementPartyField(field_mixin('party.party'), model.CoopSQL,
        model.CoopView):
    'Endorsement Party Field'

    __name__ = 'endorsement.party.field'


class EndorsementAddressField(field_mixin('party.address'), model.CoopSQL,
        model.CoopView):
    'Endorsement Address Field'

    __name__ = 'endorsement.party.address.field'


class EndorsementRelationField(field_mixin('party.relation'), model.CoopSQL,
        model.CoopView):
    'Endorsement Relations Field'

    __name__ = 'endorsement.party.relation.field'
