from trytond.pool import Pool

from .process import *
from .endorsement import *


def register():
    Pool.register(
        Endorsement,
        EndorsementPartUnion,
        EndorsementSet,
        Process,
        EndorsementFindProcess,
        module='endorsement_set_process', type_='model')

    Pool.register(
        EndorsementStartProcess,
        module='endorsement_set_process', type_='wizard')
