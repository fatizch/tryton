from trytond.pool import Pool
from .commission import *
from .rule_engine import *


def register():
    Pool.register(
        Plan,
        PlanLines,
        RuleEngineRuntime,
        RuleEngine,
        module='commission_insurance_rule_engine', type_='model')
