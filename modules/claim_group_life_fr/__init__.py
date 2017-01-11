# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import claim
import benefit
import rule_engine


def register():
    Pool.register(
        benefit.BenefitRule,
        claim.Loss,
        claim.Service,
        claim.IndemnificationDetail,
        claim.HospitalisationPeriod,
        rule_engine.RuleEngineRuntime,
        module='claim_group_life_fr', type_='model')
