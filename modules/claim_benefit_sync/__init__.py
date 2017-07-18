# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import benefit
import claim


def register():
    Pool.register(
        benefit.Benefit,
        benefit.BenefitDependencyRelation,
        claim.Loss,
        claim.Service,
        module='claim_benefit_sync', type_='model')
