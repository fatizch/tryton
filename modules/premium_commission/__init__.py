from trytond.pool import Pool

from .contract import *
from .commission import *


def register():
    Pool.register(
        Contract,
        CommissionPlan,
        CommissionPlanFee,
        Agent,
        AgentFee,
        CreateAgentsAsk,
        module='premium_commission', type_='model')
    Pool.register(
        CreateAgents,
        module='premium_commission', type_='wizard')
