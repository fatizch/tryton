from trytond.pool import Pool

from .payment import *


def register():
    Pool.register(
        Payment,
        module='account_payment_clearing_contract', type_='model')
