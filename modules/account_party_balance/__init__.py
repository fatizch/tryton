# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import move


def register():
    Pool.register(
        move.MoveLine,
        move.PartyBalance,
        move.PartyBalanceLine,
        module='account_party_balance', type_='model')
    Pool.register(
        move.OpenPartyBalance,
        module='account_party_balance', type_='wizard')
