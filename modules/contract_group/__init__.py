# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .offered import *
from .contract import *
from .benefit import *
from .party import *


def register():
    Pool.register(
        Product,
        OptionDescription,
        Benefit,
        Contract,
        Option,
        CoveredElement,
        Party,
        module='contract_group', type_='model')
