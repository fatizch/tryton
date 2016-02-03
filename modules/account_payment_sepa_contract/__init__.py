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
        module='account_payment_sepa_contract', type_='model')
