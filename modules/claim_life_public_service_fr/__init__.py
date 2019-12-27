# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool


def register():
    Pool.register(
        module='claim_life_public_service_fr', type_='model')
