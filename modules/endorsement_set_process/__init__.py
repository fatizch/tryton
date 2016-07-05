# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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
