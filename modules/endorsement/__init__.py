from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *


def register():
    Pool.register(
        EndorsementDefinition,
        EndorsementPart,
        EndorsementDefinitionPartRelation,
        Product,
        EndorsementDefinitionProductRelation,
        Contract,
        ContractOption,
        Endorsement,
        EndorsementContract,
        EndorsementContractField,
        EndorsementOption,
        EndorsementOptionField,
        SelectEndorsement,
        BasicPreview,
        module='endorsement', type_='model')

    Pool.register(
        StartEndorsement,
        OpenContractAtApplicationDate,
        module='endorsement', type_='wizard')
