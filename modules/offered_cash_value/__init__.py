# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .offered import *


def register():
    Pool.register(
        # From file offered :
        CashValueRule,
        Product,
        OptionDescription,
        module='offered_cash_value', type_='model')
