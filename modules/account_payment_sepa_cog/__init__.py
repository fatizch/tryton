from trytond.pool import Pool

from .batch import *
from .payment import *
from .bank import *
from .test_case import *
from .account import *
from .party import *


def register():
    Pool.register(
        Party,
        PaymentTreatmentBatch,
        # from payment
        Payment,
        Mandate,
        Group,
        Bank,
        BankAccountNumber,
        InvoiceLine,
        Journal,
        # Test case
        TestCaseModel,
        Configuration,
        Message,
        module='account_payment_sepa_cog', type_='model')
