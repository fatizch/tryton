# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import benefit
import claim
import rule_engine
import wizard


def register():
    Pool.register(
        benefit.LossDescription,
        benefit.DeductionPeriodKind,
        benefit.LossDescriptionDeductionPeriodKindRelation,
        claim.Loss,
        claim.DeductionPeriod,
        wizard.DeductionPeriodDisplay,
        rule_engine.RuleEngineRuntime,
        module='claim_deduction_period', type_='model')
    Pool.register(
        benefit.BenefitRule,
        wizard.IndemnificationDefinition,
        module='claim_deduction_period', type_='model',
        depends=['claim_indemnification'])
    Pool.register(
        wizard.CreateIndemnification,
        module='claim_deduction_period', type_='wizard',
        depends=['claim_indemnification'])
