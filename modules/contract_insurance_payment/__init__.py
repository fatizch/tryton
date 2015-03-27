from trytond.pool import Pool

from .payment import *
from .configuration import *
from .offered import *


def register():
    Pool.register(
        Payment,
        Journal,
        Configuration,
        Product,
        module='contract_insurance_payment', type_='model')
