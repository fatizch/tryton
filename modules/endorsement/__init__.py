# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import endorsement
import offered
import wizard
import event
import document
import party
import group


def register():
    Pool.register(
        endorsement.EndorsementConfiguration,
        offered.EndorsementSubState,
        offered.EndorsementDefinition,
        endorsement.OfferedConfiguration,
        offered.EndorsementPart,
        offered.EndorsementDefinitionPartRelation,
        offered.Product,
        offered.EndorsementDefinitionProductRelation,
        endorsement.Contract,
        endorsement.ContractOption,
        endorsement.ContractOptionVersion,
        endorsement.ContractActivationHistory,
        endorsement.ContractExtraData,
        endorsement.ContractContact,
        endorsement.Endorsement,
        endorsement.EndorsementContract,
        offered.EndorsementContractField,
        endorsement.EndorsementOption,
        offered.EndorsementOptionField,
        endorsement.EndorsementOptionVersion,
        offered.EndorsementOptionVersionField,
        endorsement.EndorsementActivationHistory,
        offered.EndorsementActivationHistoryField,
        endorsement.EndorsementContact,
        offered.EndorsementContactField,
        endorsement.EndorsementExtraData,
        offered.EndorsementExtraDataField,
        wizard.SelectEndorsement,
        wizard.DummyStep,
        wizard.RecalculateContract,
        wizard.ChangeContractStartDate,
        wizard.ReactivateContract,
        offered.EndorsementDefinitionGroupRelation,
        wizard.ChangeContractExtraData,
        wizard.ManageOptions,
        wizard.OptionDisplayer,
        wizard.TerminateContract,
        wizard.VoidContract,
        wizard.ChangeContractSubscriber,
        wizard.ManageContacts,
        wizard.ContactDisplayer,
        wizard.BasicPreview,
        wizard.EndorsementSelectDeclineReason,
        event.EndorsementDefinitionReportTemplate,
        endorsement.ReportTemplate,
        event.EventTypeAction,
        event.EventLog,
        document.DocumentDescription,
        group.Group,
        module='endorsement', type_='model')

    Pool.register(
        wizard.StartEndorsement,
        wizard.OpenContractAtApplicationDate,
        wizard.EndorsementDecline,
        endorsement.OpenGeneratedEndorsements,
        document.ReceiveDocument,
        party.PartyReplace,
        module='endorsement', type_='wizard')
