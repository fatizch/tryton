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
