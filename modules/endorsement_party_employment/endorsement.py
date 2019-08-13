# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.transaction import Transaction

from trytond.modules.coog_core import model, fields
from trytond.modules.endorsement.endorsement import relation_mixin


__all__ = [
    'EndorsementPartyEmployment',
    'EndorsementPartyEmploymentVersion',
    'Employment',
    'EmploymentVersion',
    'EndorsementParty',
    ]


class EndorsementPartyEmployment(relation_mixin('endorsement.party.'
        'employment.field', 'employment', 'party.employment', 'Employments'),
        model.CoogSQL, model.CoogView, metaclass=PoolMeta):
    'Endorsement Party Employment'
    __name__ = 'endorsement.party.employment'

    versions = fields.One2Many('endorsement.party.employment.version',
        'endorsement_party_employment', 'Endorsement Party Employment',
        delete_missing=True)
    endorsement_party = fields.Many2One('endorsement.party',
        'Endorsement Party', ondelete='CASCADE', required=True, select=True)
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')

    @classmethod
    def __setup__(cls):
        super(EndorsementPartyEmployment, cls).__setup__()
        cls._error_messages.update({'new_employment': 'New Employment'})

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.party_endorsement.definition.id

    def get_rec_name(self, name):
        if self.employment:
            return self.employment.rec_name
        return self.raise_user_error('new_employment',
            raise_exception=False)

    @classmethod
    def updated_struct(cls, employment):
        return {}

    def apply_values(self):
        values = super(EndorsementPartyEmployment, self).apply_values()
        versions = []
        for version in self.versions:
            versions.append(version.apply_values())

        if versions:
            new = values[2]
            new['versions'] = versions
            values = (values[0], values[1], new)

        return values


class EndorsementPartyEmploymentVersion(
    relation_mixin('endorsement.party.employment.version.field', 'version',
    'party.employment.version', 'Versions'), model.CoogSQL, model.CoogView,
        metaclass=PoolMeta):
    'Endorsement Party Employment Version'
    __name__ = 'endorsement.party.employment.version'

    endorsement_party_employment = fields.Many2One(
        'endorsement.party.employment',
        'Endorsement Party Employment', required=True, select=True,
        ondelete='CASCADE')


class Employment(metaclass=PoolMeta):
    __name__ = 'party.employment'
    _history = True


class EmploymentVersion(metaclass=PoolMeta):
    __name__ = 'party.employment.version'
    _history = True


class EndorsementParty(metaclass=PoolMeta):
    __name__ = 'endorsement.party'

    employments = fields.One2Many('endorsement.party.employment',
        'endorsement_party', 'Endorsements', delete_missing=True)

    def apply_values(self):
        values = super(EndorsementParty, self).apply_values()
        employments = []
        for employment in self.employments:
            employments.append(employment.apply_values())
        if employments:
            values['employments'] = employments

        return values
