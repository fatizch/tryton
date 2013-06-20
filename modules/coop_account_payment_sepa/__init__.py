from trytond.pool import Pool

from .payment import *


def register():
    Pool.register(
        # from payment
        Journal,
        Group,
        Payment,
        module='coop_account_payment', type_='model')
