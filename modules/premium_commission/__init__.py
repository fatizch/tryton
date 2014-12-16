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
        module='premium_commission', type_='model')
