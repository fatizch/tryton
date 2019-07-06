# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import rule_engine
from . import offered
from . import package
from . import coverage
from . import test_case
from . import batch
from . import exclusion
from . import extra_premium
from . import party
from . import api


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
        offered.ExtraData,
        package.Package,
        batch.ProductValidationBatch,
        rule_engine.RuleEngineExtraData,
        rule_engine.RuleEngine,
        exclusion.ExclusionKind,
        exclusion.ExclusionKindGroup,
        extra_premium.ExtraPremiumKind,
        rule_engine.RuleEngineRuntime,
        test_case.TestCaseModel,
        module='offered_insurance', type_='model')
    Pool.register(
        party.PartyReplace,
        module='offered_insurance', type_='wizard')

    Pool.register(
        api.APIProduct,
        module='offered_insurance', type_='model', depends=['api'])
