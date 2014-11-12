from trytond.pool import Pool
from .offered import *
from .endorsement import *
from .wizard import *


def register():
    Pool.register(
        EndorsementPart,
        EndorsementBeneficiaryField,
        Beneficiary,
        EndorsementContract,
        EndorsementCoveredElementOption,
        EndorsementBeneficiary,
        OptionBeneficiaryDisplayer,
        ManageBeneficiaries,
        module='endorsement_life', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_life', type_='wizard')
