from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *
from .contract import *
from .configuration import *


def register():
    Pool.register(
        BillingInformation,
        Contract,
        Endorsement,
        EndorsementContract,
        EndorsementBillingInformation,
        EndorsementBillingInformationField,
        EndorsementDefinition,
        EndorsementPart,
        ChangeBillingInformation,
        ContractDisplayer,
        BasicPreview,
        RemoveOption,
        Configuration,
        module='endorsement_insurance_invoice', type_='model')

    Pool.register(
        StartEndorsement,
        ChangeBillingAccount,
        module='endorsement_insurance_invoice', type_='wizard')
