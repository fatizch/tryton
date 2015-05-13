from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *


def register():
    Pool.register(
        Configuration,
        EndorsementSubState,
        EndorsementDefinition,
        EndorsementPart,
        EndorsementDefinitionPartRelation,
        EndorsementPartMethodRelation,
        Product,
        EndorsementDefinitionProductRelation,
        Contract,
        ContractOption,
        ContractActivationHistory,
        ContractExtraData,
        Endorsement,
        EndorsementContract,
        EndorsementContractField,
        EndorsementOption,
        EndorsementOptionField,
        EndorsementActivationHistory,
        EndorsementActivationHistoryField,
        EndorsementExtraData,
        EndorsementExtraDataField,
        SelectEndorsement,
        DummyStep,
        ChangeContractStartDate,
        ChangeContractExtraData,
        TerminateContract,
        VoidContract,
        BasicPreview,
        EndorsementSelectDeclineReason,
        ReportTemplate,
        module='endorsement', type_='model')

    Pool.register(
        StartEndorsement,
        OpenContractAtApplicationDate,
        EndorsementDecline,
        module='endorsement', type_='wizard')
