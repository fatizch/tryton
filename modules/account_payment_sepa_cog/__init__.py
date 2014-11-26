from trytond.pool import Pool

from .payment import *
from .bank import *
from .test_case import *
from .party import *


def register():
    Pool.register(
        Party,
        # from payment
        Mandate,
        Bank,
        BankAccountNumber,
        # Test case
        TestCaseModel,
        module='account_payment_sepa_cog', type_='model')
