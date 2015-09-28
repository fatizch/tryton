from trytond.pool import Pool
from .contract import *
from .commission import *
from .invoice import *
from .event import *


def register():
    Pool.register(
        Contract,
        ContractOption,
        PlanLines,
        Commission,
        Plan,
        Agent,
        Invoice,
        Event,
        module='commission_insurance_prepayment', type_='model')
