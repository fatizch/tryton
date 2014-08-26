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
        PaymentDateSelection,
        PaymentTreatmentBatch,
        PaymentCreationBatch,
        Configuration,
        module='account_payment_cog', type_='model')
    Pool.register(
        SynthesisMenuOpen,
        PaymentDateModification,
        module='account_payment_cog', type_='wizard')
