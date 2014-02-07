from trytond.pool import Pool
from .billing import *
from .account import *
from .party import *
from .payment_term import *
from .contract import *
from .offered import *


def register():
    Pool.register(
        # From payment_term
        PaymentTerm,
        PaymentTermFeeRelation,
        PaymentTermLine,
        # From billing
        PaymentMethod,
        BillingData,
        BillingPeriod,
        Premium,
        PremiumTaxRelation,
        PremiumFeeRelation,
        ContractDoBillingParameters,
        ContractDoBillingBill,
        #From Offered
        Product,
        ProductPaymentMethodRelation,
        OptionDescription,
        # From Contract
        Contract,
        Option,
        CoveredElement,
        CoveredData,
        # From party
        Party,
        # From account
        MoveBreakdown,
        Move,
        MoveLine,
        TaxDesc,
        FeeDesc,
        module='billing_individual', type_='model')

    Pool.register(
        ContractDoBilling,
        module='billing_individual', type_='wizard')
