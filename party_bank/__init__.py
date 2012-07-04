from trytond.pool import Pool
from .party import *
from .bank import *


def register():
    Pool.register(
        Party,
        Bank,
        BankAccountNumber,
        BankAccount,
        module='party_bank', type_='model')
