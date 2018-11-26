# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import claim
from . import benefit
from . import rule_engine


def register():
    Pool.register(
        benefit.BenefitRule,
        claim.Loss,
        claim.IndemnificationDetail,
        claim.HospitalisationPeriod,
        rule_engine.RuleEngineRuntime,
        module='claim_group_life_fr', type_='model')
