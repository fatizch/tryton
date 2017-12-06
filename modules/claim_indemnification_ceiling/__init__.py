# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import claim
import benefit
import rule_engine


def register():
    Pool.register(
        claim.Indemnification,
        claim.ClaimService,
        benefit.Benefit,
        benefit.BenefitRule,
        rule_engine.RuleEngine,
        module='claim_indemnification_ceiling', type_='model')
