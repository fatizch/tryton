from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *
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
        ChangeDirectDebitAccount,
        ContractDisplayer,
        BasicPreview,
        NewCoveredElement,
        NewOptionOnCoveredElement,
        RemoveOption,
        ModifyCoveredElementInformation,
        ManageExtraPremium,
        ChangeContractStartDate,
        ChangeContractExtraData,
        ChangeContractSubscriber,
        TerminateContract,
        VoidContract,
        ManageOptions,
        Configuration,
        module='endorsement_insurance_invoice', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_insurance_invoice', type_='wizard')
