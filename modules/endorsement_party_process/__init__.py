# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import process
from . import wizard


def register():
    Pool.register(
        process.Process,
        process.EndorsementPartyFindProcess,
        process.EndorsementFindProcess,
        process.Party,
        wizard.AskNextEndorsementChoice,
        module='endorsement_party_process', type_='model')
    Pool.register(
        process.EndorsementPartyStartProcess,
        wizard.AskNextEndorsement,
        module='endorsement_party_process', type_='wizard')
