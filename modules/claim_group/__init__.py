# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .offered import *
from .benefit import *
from .claim import *


def register():
    Pool.register(
        OptionDescription,
        Benefit,
        Claim,
        module='claim_group', type_='model')
