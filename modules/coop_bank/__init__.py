from trytond.pool import Pool
from .party import *
from .bank import *
from .migration import *
from .test_case import *


def register():
    Pool.register(
        Party,
        Bank,
        BankAccount,
        BankAccountNumber,
        # from test_case
        TestCaseModel,
        module='coop_bank', type_='model')
