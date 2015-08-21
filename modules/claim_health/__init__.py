from trytond.pool import Pool
from .claim import *


def register():
    Pool.register(
        HealthLoss,
        Loss,
        Claim,
        ClaimService,
        module='claim_health', type_='model')
