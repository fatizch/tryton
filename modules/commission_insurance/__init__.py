from trytond.pool import Pool
from .contract import *
from .commission import *
from .invoice import *
from .party import *
from .product import *


def register():
    Pool.register(
        Contract,
        Commission,
        PlanLines,
        Plan,
        PlanRelation,
        PlanLinesCoverageRelation,
        Agent,
        InvoiceLine,
        Party,
        Broker,
        Product,
        Template,
        Uom,
        CreateAgentsParties,
        CreateAgentsAsk,
        module='commission_insurance', type_='model')
    Pool.register(
        CreateAgents,
        module='commission_insurance', type_='wizard')
