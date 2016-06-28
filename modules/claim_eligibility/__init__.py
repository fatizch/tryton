from trytond.pool import Pool
from .benefit import *
from .claim import *


def register():
    Pool.register(
        Benefit,
        BenefitEligibilityRule,
        Claim,
        ClaimService,
        module='claim_eligibility', type_='model')
