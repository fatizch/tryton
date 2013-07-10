from trytond.pool import Pool
from trytond.modules.coop_utils import export
from .billing import *
from .account import *
from .party import *
from .payment_rule import *


def register():
    Pool.register(
        # from payment_rule
        PaymentRule,
        PaymentRuleFeeRelation,
        PaymentRuleLine,
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
        TaxDesc,
        FeeDesc,
        Sequence,
        FiscalYear,
        Company,
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

    export.add_export_to_model([
            ('account.account', ('code', 'name')),
            ('account.fiscalyear', ('code', )),
            ('account.period', ('code', )),
            ('company.company', ('party.code', )),
            ('account.tax', ('name', )),
            ('account.account.type', ('name', )),
            ], 'billing')
