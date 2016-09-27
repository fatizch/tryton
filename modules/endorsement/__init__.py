# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *
from .event import *
from .document import *


def register():
    Pool.register(
        EndorsementConfiguration,
        EndorsementSubState,
        EndorsementDefinition,
        OfferedConfiguration,
        EndorsementPart,
        EndorsementDefinitionPartRelation,
        Product,
        EndorsementDefinitionProductRelation,
        Contract,
        ContractOption,
        ContractOptionVersion,
        ContractActivationHistory,
        ContractExtraData,
        ContractContact,
        Endorsement,
        EndorsementContract,
        EndorsementContractField,
        EndorsementOption,
        EndorsementOptionField,
        EndorsementOptionVersion,
        EndorsementOptionVersionField,
        EndorsementActivationHistory,
        EndorsementActivationHistoryField,
        EndorsementContact,
        EndorsementContactField,
        EndorsementExtraData,
        EndorsementExtraDataField,
        SelectEndorsement,
        DummyStep,
        RecalculateContract,
        ChangeContractStartDate,
        ReactivateContract,
        ChangeContractExtraData,
        ManageOptions,
        OptionDisplayer,
        TerminateContract,
        VoidContract,
        ChangeContractSubscriber,
        ManageContacts,
        ContactDisplayer,
        BasicPreview,
        EndorsementSelectDeclineReason,
        EndorsementDefinitionReportTemplate,
        ReportTemplate,
        EventTypeAction,
        EventLog,
        DocumentDescription,
        module='endorsement', type_='model')

    Pool.register(
        StartEndorsement,
        OpenContractAtApplicationDate,
        EndorsementDecline,
        OpenGeneratedEndorsements,
        ReceiveDocument,
        module='endorsement', type_='wizard')
