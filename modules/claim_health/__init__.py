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
        ModifyCoveredElement,
        CoveredElementDisplayer,
        module='claim_health', type_='model')
