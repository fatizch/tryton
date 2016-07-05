# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .move import *


def register():
    Pool.register(
        MoveLine,
        PartyBalance,
        PartyBalanceLine,
        module='account_party_balance', type_='model')
    Pool.register(
        OpenPartyBalance,
        module='account_party_balance', type_='wizard')
