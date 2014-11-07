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
        InvoiceLine,
        Party,
        Broker,
        module='commission_insurance', type_='model')
