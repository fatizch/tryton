# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .contract import *


def register():
    Pool.register(
        # from contract
        Contract,
        module='contract_life_process', type_='model')
