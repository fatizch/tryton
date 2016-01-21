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
