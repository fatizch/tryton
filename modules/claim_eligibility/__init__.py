# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .benefit import *
from .claim import *
from .wizard import *


def register():
    Pool.register(
        Benefit,
        BenefitEligibilityRule,
        Claim,
        ClaimService,
        ClaimIndemnification,
        ExtraData,
        module='claim_eligibility', type_='model')
    Pool.register(
        ManualValidationEligibility,
        module='claim_eligibility', type_='wizard')
