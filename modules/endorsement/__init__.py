from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *
from .event import *


def register():
    Pool.register(
        Configuration,
        EndorsementSubState,
        EndorsementDefinition,
        EndorsementPart,
        EndorsementDefinitionPartRelation,
        Product,
        EndorsementDefinitionProductRelation,
        Contract,
        ContractOption,
        ContractOptionVersion,
        ContractActivationHistory,
        ContractExtraData,
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
        ChangeContractStartDate,
        ChangeContractExtraData,
        ManageOptions,
        OptionDisplayer,
        TerminateContract,
        VoidContract,
        ChangeContractSubscriber,
        BasicPreview,
        EndorsementSelectDeclineReason,
        EndorsementDefinitionReportTemplate,
        ReportTemplate,
        EventTypeAction,
        EventLog,
        module='endorsement', type_='model')

    Pool.register(
        StartEndorsement,
        OpenContractAtApplicationDate,
        EndorsementDecline,
        module='endorsement', type_='wizard')
