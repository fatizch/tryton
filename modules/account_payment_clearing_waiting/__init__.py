from trytond.pool import Pool

from .payment import *

def register():
    Pool.register(
        Payment,
        Journal,
        module='account_payment_clearing_waiting', type_='model')
