# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import benefit
from . import claim
from . import contract
from . import rule_engine
from . import wizard


def register():
    Pool.register(
        benefit.Benefit,
        benefit.BenefitCompanyProduct,
        benefit.BenefitRule,
        benefit.BenefitRuleIndemnification,
        benefit.BenefitRuleDeductible,
        benefit.BenefitRuleRevaluation,
        contract.Option,
        contract.OptionVersion,
        contract.OptionBenefit,
        rule_engine.RuleEngineRuntime,
        claim.ClaimService,
        claim.Indemnification,
        claim.ClaimServiceExtraDataRevision,
        wizard.IndemnificationDefinition,
        wizard.TransferServicesContracts,
        wizard.TransferServicesBenefits,
        wizard.TransferServicesBenefitLine,
        module='claim_indemnification_group', type_='model')

    Pool.register(
        wizard.CreateIndemnification,
        wizard.TransferServices,
        module='claim_indemnification_group', type_='wizard')
