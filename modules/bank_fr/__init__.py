from trytond.pool import Pool
from .bank import *


def register():
    Pool.register(
        Bank,
        BankAccountNumber,
        module='bank_fr', type_='model')
