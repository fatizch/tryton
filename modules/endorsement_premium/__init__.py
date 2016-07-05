# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .endorsement import *
from .wizard import *


def register():
    Pool.register(
        ContractFee,
        Premium,
        EndorsementContract,
        PreviewContractPremiums,
        ContractPreview,
        ContractPreviewPremium,
        module='endorsement_premium', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_premium', type_='wizard')
