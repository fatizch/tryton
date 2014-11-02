from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *


def register():
    Pool.register(
        CoveredElement,
        ExtraPremium,
        Endorsement,
        EndorsementContract,
        EndorsementCoveredElement,
        EndorsementCoveredElementOption,
        EndorsementCoveredElementField,
        EndorsementExtraPremium,
        EndorsementExtraPremiumField,
        EndorsementPart,
        NewCoveredElement,
        NewOptionOnCoveredElement,
        module='endorsement_insurance', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_insurance', type_='wizard')
