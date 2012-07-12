from trytond.pool import Pool
from .party import *
from .bank import *


def register():
    Pool.register(
        Party,
        Bank,
        BankAccount,
        BankAccountNumber,
        module='party_bank', type_='model')
