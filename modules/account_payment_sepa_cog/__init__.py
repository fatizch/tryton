from trytond.pool import Pool

from .payment import *
from .bank import *
from .test_case import *


def register():
    Pool.register(
        # from payment
        Mandate,
        # from bank
        BankAccountNumber,
        # Test case
        TestCaseModel,
        module='account_payment_sepa_cog', type_='model')
