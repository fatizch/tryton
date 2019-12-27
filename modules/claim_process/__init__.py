# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import claim
from . import process
from . import document


def register():
    Pool.register(
        claim.Claim,
        claim.Loss,
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
