# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .payment import *
from .configuration import *
from .offered import *
from .move import *
from .event import *
from .contract import *


def register():
    Pool.register(
        Payment,
        Journal,
        Configuration,
        Product,
        JournalFailureAction,
        BillingMode,
        MoveLine,
        EventLog,
        Contract,
        module='contract_insurance_payment', type_='model')
