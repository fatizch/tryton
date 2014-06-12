from trytond.pool import Pool

from .payment import *
from .bank import *


def register():
    Pool.register(
        # from payment
        Journal,
        Mandate,
        # from bank
        BankAccountNumber,
        module='account_payment_sepa_cog', type_='model')
