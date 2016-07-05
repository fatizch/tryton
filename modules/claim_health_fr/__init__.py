# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .claim import *


def register():
    Pool.register(
        HealthLoss,
        Claim,
        module='claim_health_fr', type_='model')
