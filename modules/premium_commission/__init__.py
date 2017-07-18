# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import contract
import commission


def register():
    Pool.register(
        contract.Contract,
        commission.CommissionPlan,
        commission.CommissionPlanFee,
        commission.Agent,
        commission.AgentFee,
        commission.CreateAgentsAsk,
        module='premium_commission', type_='model')
    Pool.register(
        commission.CreateAgents,
        module='premium_commission', type_='wizard')
