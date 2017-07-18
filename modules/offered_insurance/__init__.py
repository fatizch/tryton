# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import rule_engine
import offered
import coverage
import process
import test_case
import batch
import exclusion
import extra_premium
import party


def register():
    Pool.register(
        party.Party,
        party.Insurer,
        party.InsurerDelegation,
        offered.ItemDescription,
        coverage.OptionDescription,
        offered.Product,
        offered.ItemDescSubItemDescRelation,
        offered.ItemDescriptionExtraDataRelation,
        offered.CoveredElementEndReason,
        offered.ItemDescriptionEndReasonRelation,
        batch.ProductValidationBatch,
        rule_engine.RuleEngineExtraData,
        rule_engine.RuleEngine,
        exclusion.ExclusionKind,
        extra_premium.ExtraPremiumKind,
        rule_engine.RuleEngineRuntime,
        process.ProcessProductRelation,
        process.Process,
        test_case.TestCaseModel,
        module='offered_insurance', type_='model')
    Pool.register(
        party.PartyReplace,
        module='offered_insurance', type_='wizard')
