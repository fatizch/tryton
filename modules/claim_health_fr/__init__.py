from trytond.pool import Pool
from .claim import *


def register():
    Pool.register(
        HealthLoss,
        Claim,
        module='claim_health_fr', type_='model')
