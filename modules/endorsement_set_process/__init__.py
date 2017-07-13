# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import process
import endorsement


def register():
    Pool.register(
        endorsement.Endorsement,
        endorsement.EndorsementPartUnion,
        endorsement.EndorsementSet,
        process.Process,
        process.EndorsementFindProcess,
        module='endorsement_set_process', type_='model')

    Pool.register(
        process.EndorsementStartProcess,
        module='endorsement_set_process', type_='wizard')
