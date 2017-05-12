# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import contract


def register():
    Pool.register(
        contract.Contract,
        module='contract_insurance_suspension_dunning', type_='model')
