from trytond.pool import Pool
from .billing import *
from .account import *


def register():
    Pool.register(
        # From file billing :
        PaymentMethod,
        BillingManager,
        BillingPeriod,
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
        PaymentTerm,
        TaxDesc,
        FeeDesc,
        # from account
        Move,
        module='billing', type_='model')

    Pool.register(
        BillingProcess,
        module='billing', type_='wizard')
