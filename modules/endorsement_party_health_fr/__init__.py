from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *


def register():
    Pool.register(
        HealthComplement,
        EndorsementHealthComplementField,
        EndorsementPartyHealthComplement,
        EndorsementParty,
        ChangePartyHealthComplement,
        module='endorsement_party_health_fr', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_party_health_fr', type_='wizard')
