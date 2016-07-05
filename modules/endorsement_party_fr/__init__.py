# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .wizard import *


def register():
    Pool.register(
        ChangePartyAddress,
        module='endorsement_party_fr', type_='model')
