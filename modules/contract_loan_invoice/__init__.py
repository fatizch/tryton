from trytond.pool import Pool
from .contract import *
from .offered import *
from .invoice import *


def register():
    Pool.register(
        LoanShare,
        ExtraPremium,
        Premium,
        PremiumAmount,
        PremiumAmountPerPeriod,
        Contract,
        Loan,
        AveragePremiumRateLoanDisplayer,
        DisplayLoanAveragePremiumValues,
        LoanAveragePremiumRule,
        FeeRule,
        OptionDescriptionPricingRule,
        OptionDescription,
        ProductPricingDates,
        Product,
        InvoiceLineDetail,
        module='contract_loan_invoice', type_='model')

    Pool.register(
        DisplayLoanAveragePremium,
        module='contract_loan_invoice', type_='wizard')
