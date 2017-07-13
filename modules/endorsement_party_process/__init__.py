# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import process


def register():
    Pool.register(
        process.Process,
        process.EndorsementPartyFindProcess,
        process.EndorsementFindProcess,
        process.Party,
        module='endorsement_party_process', type_='model')
    Pool.register(
        process.EndorsementPartyStartProcess,
        module='endorsement_party_process', type_='wizard')
