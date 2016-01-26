from trytond.pool import Pool
from .endorsement import *
from .wizard import *


def register():
    Pool.register(
        ContractFee,
        Premium,
        PremiumTax,
        EndorsementContract,
        PreviewContractPremiums,
        ContractPreview,
        ContractPreviewPremium,
        module='endorsement_premium', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_premium', type_='wizard')
