# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .contract import *
from .invoice import *
from .move import *
from .payment import *


def register():
    Pool.register(
        Contract,
        ContractBillingInformation,
        Invoice,
        MoveLine,
        Mandate,
        Payment,
        PaymentCreationStart,
        module='account_payment_sepa_contract', type_='model')
