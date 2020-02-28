# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import offered
from . import contract
from . import batch


def register():
    Pool.register(
        offered.Product,
        contract.Contract,
        offered.PremiumEndingRule,
        offered.OptionDescriptionPremiumRule,
        batch.CalculatePremiumsBatch,
        batch.CreateInvoiceContractBatch,
        module='contract_premium_validity', type_='model')
