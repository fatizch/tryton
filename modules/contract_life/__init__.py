# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import offered
from . import contract


def register():
    Pool.register(
        offered.OptionDescription,
        contract.Contract,
        contract.ContractOption,
        contract.CoveredElement,
        module='contract_life', type_='model')
