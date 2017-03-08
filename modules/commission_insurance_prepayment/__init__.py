# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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
    Pool.register(
        FilterCommissions,
        module='commission_insurance_prepayment', type_='wizard')
