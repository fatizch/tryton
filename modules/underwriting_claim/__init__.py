# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import underwriting
import claim
import event
import process
import rule_engine


def register():
    Pool.register(
        underwriting.UnderwritingDecisionType,
        underwriting.Underwriting,
        underwriting.UnderwritingResult,
        claim.Benefit,
        claim.Claim,
        claim.ClaimService,
        rule_engine.RuleEngine,
        rule_engine.RuleEngineRuntime,
        module='underwriting_claim', type_='model')
    Pool.register(
        claim.DeliverBenefit,
        module='underwriting_claim', type_='wizard')
    Pool.register(
        event.EventLog,
        module='underwriting_claim', type_='model',
        depends=['event_log'])
    Pool.register(
        process.UnderwritingStartFindProcess,
        module='underwriting_claim', type_='model',
        depends=['underwriting_process'])
    Pool.register(
        process.UnderwritingStart,
        module='underwriting_claim', type_='wizard',
        depends=['underwriting_process'])
