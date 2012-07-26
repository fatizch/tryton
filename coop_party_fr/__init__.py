from trytond.pool import Pool
from .address import *
from .party import *


def register():
    Pool.register(
        Address,
        Person,
        module='coop_party_fr', type_='model')
