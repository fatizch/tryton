# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import account
import commission


def register():
    Pool.register(
        account.Account,
        account.Configuration,
        commission.Commission,
        module='analytic_commission', type_='model')
