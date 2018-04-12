# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.coog_core import model
from trytond.modules.endorsement.endorsement import field_mixin


__all__ = [
    'EndorsementHealthComplementField',
    ]


class EndorsementHealthComplementField(field_mixin('health.party_complement'),
        model.CoogSQL, model.CoogView):
    'Endorsement Health Complement Field'

    __name__ = 'endorsement.party.health_complement.field'
