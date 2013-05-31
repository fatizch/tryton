from trytond.pool import Pool
from .billing import *


def register():
    Pool.register(
        # From file billing :
        PaymentMethod,
        BillingManager,
        PriceLine,
        GenericBillLine,
        Bill,
        BillParameters,
        BillDisplay,
        ProductPaymentMethodRelation,
        Product,
        Contract,
        Option,
        CoveredElement,
        CoveredData,
        TaxVersion,
        FeeVersion,
        module='billing', type_='model')

    Pool.register(
        BillingProcess,
        module='billing', type_='wizard')
