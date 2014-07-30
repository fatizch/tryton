from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *


def register():
    Pool.register(
        BillingInformation,
        ContractInvoice,
        CommissionInvoice,
        Contract,
        Endorsement,
        EndorsementContract,
        EndorsementBillingInformation,
        EndorsementBillingInformationField,
        EndorsementDefinition,
        EndorsementPart,
        PreviewChanges,
        ChangeBillingInformation,
        module='endorsement_insurance_invoice', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_insurance_invoice', type_='wizard')
