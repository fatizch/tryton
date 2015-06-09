from trytond.pool import Pool
from .commission import *
from .rule_engine import *


def register():
    Pool.register(
        PrepaymentPaymentDateRule,
        Plan,
        PlanLines,
        RuleEngineRuntime,
        module='commission_prepayment_rule_engine', type_='model')
