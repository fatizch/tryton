# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import contract
import rule_engine
import party
import test_case
import wizard
import service
import contact_type
import configuration
import offered
import batch
import event
import notification

from contract import _STATES, _DEPENDS
from contract import _CONTRACT_STATUS_STATES, _CONTRACT_STATUS_DEPENDS


__all__ = [
    '_STATES',
    '_DEPENDS',
    '_CONTRACT_STATUS_STATES',
    '_CONTRACT_STATUS_DEPENDS',
    ]


def register():
    Pool.register(
        offered.Product,
        contract.ContractSubStatus,
        configuration.Configuration,
        contract.Contract,
        contract.ActivationHistory,
        contract.ContractOption,
        contract.ContractOptionVersion,
        batch.ContractEndDateTerminationBatch,
        contract.ContractExtraDataRevision,
        contract.ContractSelectStartDate,
        service.ContractService,
        rule_engine.RuleEngineRuntime,
        party.Party,
        test_case.TestCaseModel,
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
        event.EventLog,
        module='contract', type_='model')
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
        party.PartyReplace,
        module='contract', type_='wizard')