# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import underwriting
from . import claim
from . import rule_engine


def register():
    Pool.register(
        underwriting.UnderwritingDecisionType,
        underwriting.UnderwritingResult,
        claim.BenefitRule,
        claim.Service,
        claim.Indemnification,
        claim.IndemnificationDefinition,
        rule_engine.RuleEngineRuntime,
        module='underwriting_claim_indemnification', type_='model')
    Pool.register(
        claim.CreateIndemnification,
        module='underwriting_claim_indemnification', type_='wizard')
