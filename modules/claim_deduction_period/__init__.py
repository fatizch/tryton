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
        benefit.BenefitRule,
        claim.Loss,
        claim.DeductionPeriod,
        wizard.DeductionPeriodDisplay,
        wizard.IndemnificationDefinition,
        rule_engine.RuleEngineRuntime,
        module='claim_deduction_period', type_='model')
    Pool.register(
        wizard.CreateIndemnification,
        module='claim_deduction_period', type_='wizard')
