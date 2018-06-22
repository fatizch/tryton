# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import claim
import rule_engine
import benefit
import contract
import extra_data
import wizard


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

