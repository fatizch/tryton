# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import offered
from . import contract
from . import api


def register():
    Pool.register(
        offered.Product,
        offered.OptionDescription,
        offered.OptionDescriptionPremiumRule,
        contract.Contract,
        contract.CoveredElement,
        contract.ExtraPremium,
        contract.Premium,
        module='premium_insurance', type_='model')

    Pool.register(
        api.APIContractUnderwriting,
        module='premium_insurance', type_='model', depends=['api',
            'contract_underwriting'])
