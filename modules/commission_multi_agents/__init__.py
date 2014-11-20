from trytond.pool import Pool
from .commission import *
from .invoice import *


def register():
    Pool.register(
        Agent,
        Plan,
        PlanAgentRelation,
        InvoiceLine,
        module='commission_multi_agents', type_='model')
