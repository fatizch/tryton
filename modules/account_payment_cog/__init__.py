from trytond.pool import Pool

from .payment import *
from .company import *


def register():
    Pool.register(
        # from payment
        CreateReceivablePaymentStart,
        # from company
        Company,
        module='account_payment_cog', type_='model')
    Pool.register(
        CreateReceivablePayment,
        module='account_payment_cog', type_='wizard')
