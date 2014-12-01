from trytond.pool import Pool

from .party import *
from .payment import *
from .company import *
from .move import *


def register():
    Pool.register(
        Payment,
        SynthesisMenuPayment,
        SynthesisMenu,
        Company,
        MoveLine,
        PaymentInformationSelection,
        PaymentTreatmentBatch,
        PaymentCreationBatch,
        Configuration,
        Journal,
        module='account_payment_cog', type_='model')
    Pool.register(
        SynthesisMenuOpen,
        PaymentInformationModification,
        module='account_payment_cog', type_='wizard')
