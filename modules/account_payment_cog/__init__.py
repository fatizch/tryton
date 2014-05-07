from trytond.pool import Pool

from .party import *
from .payment import *
from .company import *


def register():
    Pool.register(
        # from payment
        Payment,
        CreateReceivablePaymentStart,
        # from company
        Company,
        # from contract
        SynthesisMenuPayment,
        SynthesisMenu,
        module='account_payment_cog', type_='model')
    Pool.register(
        CreateReceivablePayment,
        SynthesisMenuOpen,
        module='account_payment_cog', type_='wizard')
