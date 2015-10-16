from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *


def register():
    Pool.register(
        ContractOptionVersion,
        CoveredElement,
        CoveredElementVersion,
        ExtraPremium,
        Endorsement,
        EndorsementContract,
        EndorsementCoveredElement,
        EndorsementCoveredElementVersion,
        EndorsementCoveredElementVersionField,
        EndorsementCoveredElementOption,
        EndorsementCoveredElementField,
        EndorsementCoveredElementOptionVersion,
        EndorsementExtraPremium,
        EndorsementExtraPremiumField,
        EndorsementPart,
        NewCoveredElement,
        RemoveOptionSelector,
        RemoveOption,
        NewOptionOnCoveredElement,
        ModifyCoveredElement,
        CoveredElementDisplayer,
        ExtraPremiumDisplayer,
        ManageExtraPremium,
        ManageOptions,
        OptionDisplayer,
        OptionSelector,
        CoveredElementSelector,
        NewExtraPremium,
        VoidContract,
        module='endorsement_insurance', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_insurance', type_='wizard')
