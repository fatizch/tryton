from trytond.pool import Pool
from .party import *
from .bank import *
from .test_case import *


def register():
    Pool.register(
        # From Party
        Party,
        # From Bank
        Bank,
        BankAccount,
        BankAccountNumber,
        # from test_case
        TestCaseModel,
        module='coop_bank', type_='model')
