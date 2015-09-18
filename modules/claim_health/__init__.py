from trytond.pool import Pool
from .claim import *
from .contract import *
from .wizard import *


def register():
    Pool.register(
        HealthLoss,
        Loss,
        Claim,
        ClaimService,
        CoveredElement,
        ModifyCoveredElementInformation,
        module='claim_health', type_='model')
