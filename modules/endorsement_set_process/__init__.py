from trytond.pool import Pool

from .process import *
from .endorsement import *


def register():
    Pool.register(
        Endorsement,
        EndorsementPartUnion,
        EndorsementSet,
        Process,
        EndorsementSetApplyFindProcess,
        module='endorsement_set_process', type_='model')

    Pool.register(
        EndorsementSetApply,
        module='endorsement_set_process', type_='wizard')
