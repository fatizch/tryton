from trytond.pool import Pool
from .party import *


def register():
    Pool.register(
        Party,
        PartyIdentifier,
        module='commission_orias', type_='model')
