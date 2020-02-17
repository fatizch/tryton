# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import commission
from . import rule_engine
from . import extra_data
from . import invoice


def register():
    Pool.register(
        commission.Plan,
        commission.PlanLines,
        commission.Agent,
        rule_engine.RuleEngine,
        extra_data.ExtraData,
        extra_data.CommissionPlanExtraDataRelation,
        module='commission_insurance_rule_engine', type_='model')
    Pool.register(
        commission.PlanWithLoan,
        commission.PlanLinesWithLoan,
        invoice.InvoiceLineWithLoan,
        module='commission_insurance_rule_engine', type_='model',
        depends=['loan'])
