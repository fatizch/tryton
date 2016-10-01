# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, model
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

    @classmethod
    def __register__(cls, module):
        TableHandler = backend.get('TableHandler')

        # Migration from 1.6 : Rename definition_for_contracts to
        # next_endorsement, defined in endorsement module
        table = TableHandler(cls, module)
        if table.column_exist('definition_for_contracts'):
            table.column_rename('definition_for_contracts', 'next_endorsement')
        super(EndorsementDefinition, cls).__register__(module)

    def get_is_party(self, name):
        return any([x.is_party for x in self.endorsement_parts])

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

    @classmethod
    def __setup__(cls):
        super(EndorsementPart, cls).__setup__()
        cls.kind.selection.append(('party', 'Party'))

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


class EndorsementPartyField(field_mixin('party.party'), model.CoogSQL,
        model.CoogView):
    'Endorsement Party Field'

    __name__ = 'endorsement.party.field'


class EndorsementAddressField(field_mixin('party.address'), model.CoogSQL,
        model.CoogView):
    'Endorsement Address Field'

    __name__ = 'endorsement.party.address.field'


class EndorsementRelationField(field_mixin('party.relation'), model.CoogSQL,
        model.CoogView):
    'Endorsement Relations Field'

    __name__ = 'endorsement.party.relation.field'
