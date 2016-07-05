# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .process import *


def register():
    Pool.register(
        Process,
        EndorsementPartyFindProcess,
        EndorsementFindProcess,
        Party,
        module='endorsement_party_process', type_='model')
    Pool.register(
        EndorsementPartyStartProcess,
        module='endorsement_party_process', type_='wizard')
