from trytond.pool import PoolMeta

from trytond.modules.cog_utils import model
from trytond.modules.endorsement import field_mixin


__metaclass__ = PoolMeta
__all__ = [
    'EndorsementHealthComplementField',
    ]


class EndorsementHealthComplementField(field_mixin('health.party_complement'),
        model.CoopSQL, model.CoopView):
    'Endorsement Health Complement Field'

    __name__ = 'endorsement.party.health_complement.field'
