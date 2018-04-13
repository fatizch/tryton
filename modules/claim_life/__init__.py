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
        benefit.ExtraData,
        benefit.BeneficiaryExtraDataRelation,
        contract.ContractOption,
        claim.Claim,
        claim.Loss,
        claim.ClaimService,
        claim.ClaimBeneficiary,
        claim.ClaimServiceExtraDataRevision,
        claim.Indemnification,
        claim.DocumentRequestLine,
        rule_engine.RuleEngineRuntime,
        test_case.TestCaseModel,
        wizard.IndemnificationValidateElement,
        wizard.IndemnificationControlElement,
        wizard.IndemnificationDefinition,
        wizard.SelectService,
        module='claim_life', type_='model')
    Pool.register(
        party.PartyReplace,
        wizard.CreateIndemnification,
        wizard.PartyErase,
        module='claim_life', type_='wizard')
