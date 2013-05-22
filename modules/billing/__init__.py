from trytond.pool import Pool
from .billing import *

def register():
    Pool.register(
        # From file billing :
        PriceLine,
        BillingManager,
        GenericBillLine,
        Bill,
        BillParameters,
        BillDisplay,
        Contract,
        Option,
        CoveredElement,
        CoveredData,
        module='billing', type_='model')

    Pool.register(
        BillingProcess,
        module='billing', type_='wizard')
