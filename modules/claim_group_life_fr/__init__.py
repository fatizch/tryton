# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .claim import *
from .benefit import *
from .rule_engine import *


def register():
    Pool.register(
        BenefitRule,
        IndemnificationDetail,
        HospitalisationPeriod,
        Loss,
        RuleEngineRuntime,
        module='claim_group_life_fr', type_='model')
