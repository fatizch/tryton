# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import claim
from . import contract
from . import test_case
from . import benefit
from . import wizard
from . import rule_engine
from . import party


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
