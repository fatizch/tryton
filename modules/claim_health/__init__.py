# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .claim import *
from .contract import *
from .wizard import *
from .benefit import *


def register():
    Pool.register(
        LossDescription,
        MedicalActFamily,
        MedicalActDescription,
        HealthLoss,
        Loss,
        Claim,
        ClaimService,
        CoveredElement,
        ModifyCoveredElement,
        CoveredElementDisplayer,
        module='claim_health', type_='model')
