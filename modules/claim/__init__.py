# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import claim
from . import offered
from . import contract
from . import endorsement
from . import rule_engine
from . import party
from . import test_case
from . import global_search
from . import report_engine
from . import benefit
from . import wizard
from . import event
from . import configuration
from . import api


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
        contract.ContractVersion,
        contract.Option,
        rule_engine.RuleEngineRuntime,
        party.Party,
        party.Insurer,
        offered.Product,
        offered.OptionDescription,
        test_case.TestCaseModel,
        wizard.BenefitToDeliver,
        wizard.SelectBenefits,
        party.SynthesisMenuClaim,
        party.SynthesisMenu,
        party.InsurerDelegation,
        report_engine.ReportTemplate,
        configuration.Configuration,
        wizard.ClaimCloseReasonView,
        wizard.BenefitSelectExtraDataView,
        wizard.LossSelectExtraDataView,
        wizard.SetOriginServiceSelect,
        global_search.GlobalSearchSet,
        module='claim', type_='model')
    Pool.register(
        wizard.CloseClaim,
        wizard.DeliverBenefits,
        wizard.PropagateBenefitExtraData,
        wizard.PropagateLossExtraData,
        wizard.PartyErase,
        wizard.SetOriginService,
        party.SynthesisMenuOpen,
        party.PartyReplace,
        module='claim', type_='wizard')
    Pool.register(
        event.EventLog,
        module='claim', type_='model',
        depends=['event_log'])
    Pool.register(
        endorsement.ContractEndorsement,
        endorsement.ChangeContractClaimAccount,
        module='claim', type_='model',
        depends=['endorsement'])
    Pool.register(
        endorsement.StartEndorsement,
        module='claim', type_='wizard',
        depends=['endorsement'])

    Pool.register(
        api.APICore,
        api.APIParty,
        module='claim', type_='model', depends=['api'])
