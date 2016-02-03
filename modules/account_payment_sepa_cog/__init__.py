from trytond.pool import Pool

from .batch import *
from .payment import *
from .bank import *
from .test_case import *
from .account import *
from .party import *
from .move import *


def register():
    Pool.register(
        Party,
        PaymentTreatmentBatch,
        Payment,
        Mandate,
        Group,
        Bank,
        BankAccount,
        BankAccountNumber,
        InvoiceLine,
        Journal,
        TestCaseModel,
        Configuration,
        Message,
        PaymentCreationStart,
        MoveLine,
        module='account_payment_sepa_cog', type_='model')
    Pool.register(
        PaymentCreation,
        module='account_payment_sepa_cog', type_='wizard')
