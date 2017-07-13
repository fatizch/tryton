# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import commission
import rule_engine


def register():
    Pool.register(
        commission.PrepaymentPaymentDateRule,
        commission.Plan,
        commission.PlanLines,
        rule_engine.RuleEngineRuntime,
        module='commission_prepayment_rule_engine', type_='model')
