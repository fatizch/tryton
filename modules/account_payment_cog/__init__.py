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
        module='account_payment_cog', type_='model')
    Pool.register(
        CreateReceivablePayment,
        module='account_payment_cog', type_='wizard')
