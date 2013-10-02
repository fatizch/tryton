from trytond.pool import Pool
from .party import *
from .bank import *
from .migration import *


def register():
    Pool.register(
        Party,
        Bank,
        BankAccount,
        BankAccountNumber,
        #For temporary migration purpose
        OldBank,
        OldBankAccount,
        OldBankAccountNumber,
        module='coop_bank', type_='model')
