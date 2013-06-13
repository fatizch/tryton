from trytond.pool import Pool
from .billing import *
from .account import *
from .party import *


def register():
    Pool.register(
        # From file billing :
        PaymentMethod,
        BillingManager,
        BillingPeriod,
        PriceLine,
        PriceLineTaxRelation,
        PriceLineFeeRelation,
        BillParameters,
        BillDisplay,
        ProductPaymentMethodRelation,
        Product,
        Coverage,
        Contract,
        Option,
        CoveredElement,
        CoveredData,
        PaymentTerm,
        TaxDesc,
        FeeDesc,
        # from party
        Party,
        # from account
        Move,
        MoveLine,
        Account,
        module='billing', type_='model')

    Pool.register(
        BillingProcess,
        module='billing', type_='wizard')
