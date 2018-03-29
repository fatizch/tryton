# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import claim
import process
import document


def register():
    Pool.register(
        claim.Claim,
        process.Process,
        process.ClaimDeclarationElement,
        process.ProcessLossDescRelation,
        process.ClaimDeclareFindProcess,
        document.DocumentDescription,
        module='claim_process', type_='model')

    Pool.register(
        process.CloseClaim,
        process.ClaimDeclare,
        document.ReceiveDocument,
        module='claim_process', type_='wizard')
