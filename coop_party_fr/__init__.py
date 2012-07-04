from trytond.pool import Pool
from .address import *


def register():
    Pool.register(
        Address,
        module='coop_party_fr', type_='model')
