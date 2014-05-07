from trytond.pool import Pool
from .contract import *


def register():
    Pool.register(
        Contract,
        module='account_payment_sepa_contract', type_='model')
