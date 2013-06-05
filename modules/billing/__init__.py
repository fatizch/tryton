from trytond.pool import Pool
from .billing import *


def register():
    Pool.register(
        # From file billing :
        PaymentMethod,
        BillingManager,
        PriceLine,
        PriceLineTaxRelation,
        PriceLineFeeRelation,
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
        module='billing', type_='model')

    Pool.register(
        BillingProcess,
        module='billing', type_='wizard')
