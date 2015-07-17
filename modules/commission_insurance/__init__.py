from trytond.pool import Pool
from .contract import *
from .commission import *
from .invoice import *
from .party import *
from .payment import *
from .account import *
from .batch import *


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
        Invoice,
        Party,
        CreateAgentsParties,
        CreateAgentsAsk,
        CreateInvoiceAsk,
        Configuration,
        Fee,
        MoveLine,
        CreateCommissionInvoiceBatch,
        PostCommissionInvoiceBatch,
        module='commission_insurance', type_='model')
    Pool.register(
        CreateInvoice,
        CreateAgents,
        module='commission_insurance', type_='wizard')
