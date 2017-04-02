# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .contract import *


def register():
    Pool.register(
        Contract,
        ContractOption,
        Beneficiary,
        module='contract_life_clause', type_='model')