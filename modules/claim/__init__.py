# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import claim
import offered
import contract
import rule_engine
import party
import test_case
import global_search
import report_engine
import benefit
import wizard
import event
import configuration


def register():
    Pool.register(
        benefit.ClosingReason,
        benefit.EventDescription,
        benefit.LossDescription,
        benefit.LossDescriptionClosingReason,
        benefit.Benefit,
        benefit.EventDescriptionLossDescriptionRelation,
        benefit.BenefitLossDescriptionRelation,
        benefit.OptionDescriptionBenefitRelation,
        benefit.LossDescriptionExtraDataRelation,
        benefit.BenefitExtraDataRelation,
        claim.ClaimSubStatus,
        claim.Claim,
        claim.Loss,
        claim.ClaimService,
        claim.ClaimServiceExtraDataRevision,
        contract.Contract,
        contract.Option,
        rule_engine.RuleEngineRuntime,
        party.Party,
        offered.OptionDescription,
        test_case.TestCaseModel,
        wizard.BenefitToDeliver,
        wizard.SelectBenefits,
        party.SynthesisMenuClaim,
        party.SynthesisMenu,
        party.InsurerDelegation,
        report_engine.ReportTemplate,
        event.EventLog,
        configuration.Configuration,
        wizard.ClaimCloseReasonView,
        global_search.GlobalSearchSet,
        module='claim', type_='model')
    Pool.register(
        wizard.CloseClaim,
        wizard.DeliverBenefits,
        party.SynthesisMenuOpen,
        party.PartyReplace,
        module='claim', type_='wizard')
