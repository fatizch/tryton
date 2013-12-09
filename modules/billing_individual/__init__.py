from trytond.pool import Pool
from .billing import *
from .account import *
from .party import *
from .payment_rule import *


def register():
    Pool.register(
        # From payment_rule
        PaymentRule,
        PaymentRuleFeeRelation,
        PaymentRuleLine,
        # From billing
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
        TaxDesc,
        FeeDesc,
        # From party
        Party,
        # From account
        Move,
        MoveLine,
        module='billing_individual', type_='model')

    Pool.register(
        BillingProcess,
        module='billing_individual', type_='wizard')
