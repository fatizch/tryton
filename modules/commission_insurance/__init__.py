from trytond.pool import Pool
from .contract import *
from .commission import *
from .invoice import *
from .party import *


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
        CreateAgentsParties,
        CreateAgentsAsk,
        CreateInvoiceAsk,
        module='commission_insurance', type_='model')
    Pool.register(
        CreateInvoice,
        CreateAgents,
        module='commission_insurance', type_='wizard')
