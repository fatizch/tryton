# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import offered


def register():
    Pool.register(
        offered.CashValueRule,
        offered.Product,
        offered.OptionDescription,
        module='offered_cash_value', type_='model')
