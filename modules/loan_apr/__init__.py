from trytond.pool import Pool
from .offered import *
from .contract import *
from .loan import *


def register():
    Pool.register(
        LoanAveragePremiumRule,
        FeeRule,
        Product,
        Contract,
        LoanShare,
        Loan,
        AveragePremiumRateLoanDisplayer,
        DisplayLoanAveragePremiumValues,
        module='loan_apr', type_='model')

    Pool.register(
        DisplayLoanAveragePremium,
        module='loan_apr', type_='wizard')
