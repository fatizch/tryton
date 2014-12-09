from trytond.pool import Pool

from .payment import *
from .bank import *
from .test_case import *
from .account import *
from .party import *


def register():
    Pool.register(
        Party,
        # from payment
        Payment,
        Mandate,
        Group,
        Payment,
        Bank,
        BankAccountNumber,
        # Test case
        TestCaseModel,
        Configuration,
        module='account_payment_sepa_cog', type_='model')
