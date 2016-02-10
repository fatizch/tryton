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
        AggregatedCommission,
        Commission,
        PlanLines,
        Plan,
        PlanRelation,
        PlanLinesCoverageRelation,
        PlanCalculationDate,
        Agent,
        InvoiceLine,
        Invoice,
        Party,
        CreateAgentsParties,
        CreateAgentsAsk,
        CreateInvoiceAsk,
        SelectNewBroker,
        Configuration,
        Fee,
        MoveLine,
        OpenCommissionsSynthesisStart,
        OpenCommissionsSynthesisShow,
        OpenCommissionSynthesisYearLine,
        CreateCommissionInvoiceBatch,
        PostCommissionInvoiceBatch,
        module='commission_insurance', type_='model')
    Pool.register(
        CreateInvoice,
        CreateAgents,
        ChangeBroker,
        FilterCommissions,
        OpenCommissionsSynthesis,
        FilterAggregatedCommissions,
        module='commission_insurance', type_='wizard')
