from trytond.pool import Pool

from .payment import *
from .company import *
from .contract import *


def register():
    Pool.register(
        # from payment
        CreateReceivablePaymentStart,
        # from company
        Company,
        # from contract
        Contract,
        module='coop_account_payment', type_='model')
    Pool.register(
        CreateReceivablePayment,
        module='coop_account_payment', type_='wizard')
