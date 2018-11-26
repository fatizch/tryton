# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import claim
from . import benefit
from . import rule_engine


def register():
    Pool.register(
        claim.Indemnification,
        claim.ClaimService,
        benefit.Benefit,
        benefit.BenefitRule,
        rule_engine.RuleEngine,
        module='claim_indemnification_ceiling', type_='model')
