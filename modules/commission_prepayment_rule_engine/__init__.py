# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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
