# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import benefit
import claim
import wizard


def register():
    Pool.register(
        benefit.Benefit,
        benefit.BenefitEligibilityRule,
        claim.Claim,
        claim.ClaimService,
        claim.ClaimIndemnification,
        claim.ExtraData,
        module='claim_eligibility', type_='model')
    Pool.register(
        wizard.ManualValidationEligibility,
        wizard.ManualRejectionEligibility,
        module='claim_eligibility', type_='wizard')
