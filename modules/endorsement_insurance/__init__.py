# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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
        OptionExclusionRelation,
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
        EndorsementExclusion,
        EndorsementExclusionField,
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
        ManageExclusions,
        ManageExclusionsOptionDisplayer,
        ManageExclusionsDisplayer,
        module='endorsement_insurance', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_insurance', type_='wizard')
