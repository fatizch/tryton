# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import claim
import contract
import test_case
import benefit
import wizard
import rule_engine
import party


def register():
    Pool.register(
        benefit.Benefit,
        benefit.BenefitBeneficiaryDocument,
        benefit.LossDescription,
        contract.ContractOption,
        claim.Claim,
        claim.Loss,
        claim.ClaimService,
        claim.ClaimBeneficiary,
        claim.ClaimServiceExtraDataRevision,
        rule_engine.RuleEngineRuntime,
        test_case.TestCaseModel,
        wizard.IndemnificationValidateElement,
        wizard.IndemnificationControlElement,
        module='claim_life', type_='model')
    Pool.register(
        party.PartyReplace,
        module='claim_life', type_='wizard')