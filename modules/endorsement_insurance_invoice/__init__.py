from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *


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
        module='endorsement_insurance_invoice', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_insurance_invoice', type_='wizard')
