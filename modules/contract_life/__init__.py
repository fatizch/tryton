# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .offered import *
from .contract import *


def register():
    Pool.register(
        OptionDescription,
        Contract,
        ContractOption,
        module='contract_life', type_='model')
