from trytond.pool import Pool
from .contract import *
from .invoice import *
from .move import *


def register():
    Pool.register(
        Contract,
        ContractBillingInformation,
        Invoice,
        MoveLine,
        module='account_payment_sepa_contract', type_='model')
