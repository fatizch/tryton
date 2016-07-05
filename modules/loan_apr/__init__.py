# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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
