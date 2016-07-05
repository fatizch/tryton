# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .offered import *
from .endorsement import *
from .wizard import *


def register():
    Pool.register(
        EndorsementPart,
        EndorsementClauseField,
        Clause,
        EndorsementContract,
        EndorsementClause,
        ManageClauses,
        ClauseDisplayer,
        module='endorsement_clause', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_clause', type_='wizard')
