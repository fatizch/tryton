# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import service
import benefit


def register():
    Pool.register(
        service.ClaimService,
        benefit.BenefitRule,
        module='claim_credit', type_='model')
