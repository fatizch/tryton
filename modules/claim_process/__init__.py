# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .claim import *


def register():
    Pool.register(
        # From claim
        Claim,
        Loss,
        Process,
        ClaimDeclarationElement,
        ProcessLossDescRelation,
        ClaimDeclareFindProcess,
        module='claim_process', type_='model')

    Pool.register(
        CloseClaim,
        ClaimDeclare,
        module='claim_process', type_='wizard')
