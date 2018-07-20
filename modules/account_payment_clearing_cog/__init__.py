# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import payment
import move


def register():
    Pool.register(
        payment.Payment,
        payment.Journal,
        move.MoveLine,
        module='account_payment_clearing_cog', type_='model')
