# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import endorsement
import wizard


def register():
    Pool.register(
        endorsement.ContractFee,
        endorsement.Premium,
        endorsement.EndorsementContract,
        wizard.PreviewContractPremiums,
        wizard.ContractPreview,
        wizard.ContractPreviewPremium,
        module='endorsement_premium', type_='model')

    Pool.register(
        wizard.StartEndorsement,
        module='endorsement_premium', type_='wizard')
