# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .commission import *
from .invoice import *
from .contract import *


def register():
    Pool.register(
        Commission,
        Agent,
        AgentAgentRelation,
        Plan,
        PlanAgentRelation,
        InvoiceLine,
        Contract,
        ContractOption,
        module='commission_multi_agents', type_='model')
