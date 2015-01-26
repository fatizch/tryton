from trytond.pool import Pool
from .endorsement import *


def register():
    Pool.register(
        Configuration,
        EndorsementSet,
        Endorsement,
        EndorsementSetSelectDeclineReason,
        module='endorsement_set', type_='model')
    Pool.register(
        EndorsementSetDecline,
        module='endorsement_set', type_='wizard')
