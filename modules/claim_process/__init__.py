from trytond.pool import Pool
from .claim_process import *


def register():
    Pool.register(
        Claim,
        Loss,
        Process,
        ClaimDeclareFindProcess,
        module='claim_process', type_='model')

    Pool.register(
        ClaimDeclare,
        module='claim_process', type_='wizard')
