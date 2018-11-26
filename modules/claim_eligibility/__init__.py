# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import benefit
from . import claim
from . import rule_engine
from . import wizard


def register():
    Pool.register(
        benefit.Benefit,
        benefit.BenefitEligibilityRule,
        benefit.BenefitEligibilityDecision,
        benefit.BenefitBenefitEligibility,
        claim.Claim,
        claim.ClaimLoss,
        claim.ClaimService,
        claim.ClaimIndemnification,
        rule_engine.RuleEngineRuntime,
        wizard.ClaimServiceManualDisplay,
        module='claim_eligibility', type_='model')
    Pool.register(
        wizard.ManualValidationEligibility,
        wizard.ManualRejectionEligibility,
        module='claim_eligibility', type_='wizard')
