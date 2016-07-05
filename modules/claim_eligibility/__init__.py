# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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
