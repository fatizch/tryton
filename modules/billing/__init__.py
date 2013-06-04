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
        Move,
        module='billing', type_='model')

    Pool.register(
        BillingProcess,
        module='billing', type_='wizard')
