from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *


def register():
    Pool.register(
        EndorsementDefinition,
        EndorsementPart,
        EndorsementDefinitionPartRelation,
        EndorsementPartMethodRelation,
        Product,
        EndorsementDefinitionProductRelation,
        Contract,
        ContractOption,
        ContractActivationHistory,
        Endorsement,
        EndorsementContract,
        EndorsementContractField,
        EndorsementOption,
        EndorsementOptionField,
        EndorsementActivationHistory,
        EndorsementActivationHistoryField,
        Process,
        SelectEndorsement,
        ChangeContractStartDate,
        StartFullContractRevision,
        BasicPreview,
        module='endorsement', type_='model')

    Pool.register(
        StartEndorsement,
        OpenContractAtApplicationDate,
        module='endorsement', type_='wizard')
