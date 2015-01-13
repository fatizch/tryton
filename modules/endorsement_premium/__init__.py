from trytond.pool import Pool
from .wizard import *


def register():
    Pool.register(
        PreviewContractPremiums,
        ContractPreview,
        ContractPreviewPremium,
        module='endorsement_premium', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_premium', type_='wizard')
