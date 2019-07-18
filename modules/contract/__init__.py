# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import contract
from . import rule_engine
from . import party
from . import global_search
from . import wizard
from . import service
from . import contact_type
from . import configuration
from . import offered
from . import batch
from . import event
from . import notification
from . import test_case
from . import api

from .contract import _STATES, _DEPENDS
from .contract import _CONTRACT_STATUS_STATES, _CONTRACT_STATUS_DEPENDS


__all__ = [
    '_STATES',
    '_DEPENDS',
    '_CONTRACT_STATUS_STATES',
    '_CONTRACT_STATUS_DEPENDS',
    ]


def register():
    Pool.register(
        offered.Product,
        offered.ProductQuoteNumberSequence,
        offered.ContractDataRule,
        offered.OptionDescriptionEndingRule,
        contract.ContractSubStatus,
        configuration.Configuration,
        configuration.ConfigurationDefaultQuoteNumberSequence,
        contract.Contract,
        contract.ActivationHistory,
        contract.ContractOption,
        contract.ContractOptionVersion,
        batch.ContractEndDateTerminationBatch,
        batch.PartyAnonymizeIdentificationBatch,
        batch.TerminateContractOption,
        contract.ContractExtraDataRevision,
        contract.ContractSelectStartDate,
        service.ContractService,
        rule_engine.RuleEngineRuntime,
        rule_engine.RuleEngine,
        party.Party,
        global_search.GlobalSearchSet,
        wizard.PackageSelection,
        wizard.OptionsDisplayer,
        wizard.WizardOption,
        contact_type.ContactType,
        contact_type.ContractContact,
        party.SynthesisMenuContrat,
        party.SynthesisMenu,
        wizard.ContractActivateConfirm,
        wizard.ContractSelectDeclineReason,
        wizard.ContractStopSelectContracts,
        contract.ContractSelectHoldReason,
        wizard.ContractReactivateCheck,
        notification.ContractNotification,
        event.EventTypeAction,
        test_case.TestCaseModel,
        wizard.SelectSubStatus,
        module='contract', type_='model')
    Pool.register(
        event.EventLog,
        module='contract', type_='model',
        depends=['event_log'])
    Pool.register(
        wizard.OptionSubscription,
        party.SynthesisMenuOpen,
        contract.ContractChangeStartDate,
        wizard.ContractActivate,
        wizard.ContractDecline,
        wizard.ContractStop,
        contract.ContractHold,
        wizard.ContractReactivate,
        wizard.RelatedAttachments,
        wizard.ChangeSubStatus,
        party.PartyReplace,
        wizard.PartyErase,
        module='contract', type_='wizard')

    Pool.register(
        api.APIContract,
        api.ContractAPIRuleRuntime,
        module='contract', type_='model', depends=['api'])
