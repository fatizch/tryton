# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .commission import *
from .rule_engine import *
from .extra_data import *


def register():
    Pool.register(
        Plan,
        PlanLines,
        Agent,
        RuleEngineRuntime,
        RuleEngine,
        ExtraData,
        CommissionPlanExtraDataRelation,
        module='commission_insurance_rule_engine', type_='model')
