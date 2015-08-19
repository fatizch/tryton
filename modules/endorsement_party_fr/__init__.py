from trytond.pool import Pool
from .wizard import *


def register():
    Pool.register(
        ChangePartyAddress,
        module='endorsement_party_fr', type_='model')
