# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import payment
from . import move
from . import account


def register():
    Pool.register(
        payment.Payment,
        payment.Journal,
        move.MoveLine,
        module='account_payment_clearing_cog', type_='model')
    Pool.register(
        account.Journal,
        move.Move,
        module='account_payment_clearing_cog', type_='model',
        depends=['account_aggregate'])
