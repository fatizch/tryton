from trytond.pool import Pool

from .batch import *
from .party import *
from .payment import *
from .company import *
from .move import *


def register():
    Pool.register(
        Journal,
        RejectReason,
        JournalFailureAction,
        Payment,
        SynthesisMenuPayment,
        SynthesisMenu,
        Company,
        MoveLine,
        PaymentInformationSelection,
        PaymentTreatmentBatch,
        PaymentCreationBatch,
        Configuration,
        Group,
        Party,
        PaymentCreationStart,
        module='account_payment_cog', type_='model')
    Pool.register(
        SynthesisMenuOpen,
        PaymentInformationModification,
        PaymentCreation,
        module='account_payment_cog', type_='wizard')
