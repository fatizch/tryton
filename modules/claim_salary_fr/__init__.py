# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import claim
from . import rule_engine
from . import benefit
from . import contract
from . import extra_data
from . import wizard


def register():
    Pool.register(
        claim.Claim,
        claim.ClaimLoss,
        claim.ClaimService,
        claim.Salary,
        claim.NetCalculationRule,
        claim.NetCalculationRuleExtraData,
        claim.NetCalculationRuleFixExtraData,
        benefit.BenefitRule,
        contract.OptionBenefit,
        rule_engine.Table,
        rule_engine.DimensionValue,
        rule_engine.Cell,
        rule_engine.RuleEngineRuntime,
        rule_engine.RuleEngine,
        extra_data.ExtraData,
        wizard.StartSetContributions,
        wizard.StartSetSalaries,
        wizard.ContributionsView,
        module='claim_salary_fr', type_='model')
    Pool.register(
        wizard.SalariesComputation,
        module='claim_salary_fr', type_='wizard')
    Pool.register(
        benefit.ManageOptionBenefitsDisplayer,
        module='claim_salary_fr', type_='model',
        depends=['endorsement_option_benefit'])
