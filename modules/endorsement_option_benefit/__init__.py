# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .endorsement import *
from .benefit import *
from .wizard import *


def register():
    Pool.register(
        OptionBenefit,
        OptionDisplayer,
        ManageOptionBenefits,
        ManageOptionBenefitsDisplayer,
        EndorsementContract,
        EndorsementPart,
        EndorsementBenefitField,
        EndorsementOptionBenefit,
        EndorsementOptionVersion,
        module='endorsement_option_benefit', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_option_benefit', type_='wizard')
