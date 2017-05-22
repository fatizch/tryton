# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import claim
import benefit


def register():
    Pool.register(
        benefit.Benefit,
        claim.ClaimService,
        claim.Claim,
       module='claim_service_number', type_='model')
