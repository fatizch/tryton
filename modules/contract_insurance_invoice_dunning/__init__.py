# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import payment
from .dunning import *
from .offered import *
from .contract import *
from .account import *
from .event import *
from .invoice import *
from .batch import *


def register():
    Pool.register(
        Dunning,
        Procedure,
        Level,
        Contract,
        Product,
        MoveLine,
        EventLog,
        Invoice,
        payment.Payment,
        DunningTreatmentBatch,
        DunningCreationBatch,
        module='contract_insurance_invoice_dunning', type_='model')
