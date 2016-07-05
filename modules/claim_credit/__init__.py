# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .service import *
from .benefit import *


def register():
    Pool.register(
        ClaimService,
        BenefitRule,
        module='claim_credit', type_='model')
