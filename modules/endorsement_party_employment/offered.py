# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.coog_core import model
from trytond.modules.endorsement.endorsement import field_mixin

__all__ = [
    'EndorsementPartyEmploymentField',
    'EndorsementPartyEmploymentVersionField',
    ]


class EndorsementPartyEmploymentField(field_mixin('party.employment'),
        model.CoogSQL, model.CoogView):
    'Endorsement Party Employment Field'

    __name__ = 'endorsement.party.employment.field'


class EndorsementPartyEmploymentVersionField(field_mixin(
    'party.employment.version'), model.CoogSQL,
        model.CoogView):
    'Endorsement Party Employment Version Field'

    __name__ = 'endorsement.party.employment.version.field'
