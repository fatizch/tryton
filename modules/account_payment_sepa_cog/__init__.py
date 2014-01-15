from trytond.pool import Pool

from .payment import *


def register():
    Pool.register(
        # from payment
        Journal,
        Group,
        Payment,
        module='account_payment_sepa_cog', type_='model')
