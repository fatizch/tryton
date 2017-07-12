# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import commission
import rule_engine
import extra_data


def register():
    Pool.register(
        commission.Plan,
        commission.PlanLines,
        commission.Agent,
        rule_engine.RuleEngineRuntime,
        rule_engine.RuleEngine,
        extra_data.ExtraData,
        extra_data.CommissionPlanExtraDataRelation,
        module='commission_insurance_rule_engine', type_='model')
