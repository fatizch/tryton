# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import claim
import document


def register():
    Pool.register(
        claim.Claim,
        claim.Process,
        claim.ClaimDeclarationElement,
        claim.ProcessLossDescRelation,
        claim.ClaimDeclareFindProcess,
        document.DocumentDescription,
        module='claim_process', type_='model')

    Pool.register(
        claim.CloseClaim,
        claim.ClaimDeclare,
        document.ReceiveDocument,
        module='claim_process', type_='wizard')
