from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *
from .contract import *


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
        BasicPreview,
        RemoveOption,
        module='endorsement_insurance_invoice', type_='model')

    Pool.register(
        StartEndorsement,
        ChangeBillingAccount,
        module='endorsement_insurance_invoice', type_='wizard')
