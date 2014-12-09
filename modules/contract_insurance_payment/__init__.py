from trytond.pool import Pool

from .payment import *


def register():
    Pool.register(
        Payment,
        Journal,
        module='contract_insurance_payment', type_='model')
