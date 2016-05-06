from trytond.pool import Pool
from .claim import *


def register():
    Pool.register(
        # From claim
        Claim,
        Loss,
        Process,
        ProcessLossDescRelation,
        ClaimDeclareFindProcess,
        module='claim_process', type_='model')

    Pool.register(
        ClaimDeclare,
        module='claim_process', type_='wizard')
