# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import offered
import contract
import loan


def register():
    Pool.register(
        offered.LoanAveragePremiumRule,
        offered.FeeRule,
        offered.Product,
        contract.Contract,
        contract.LoanShare,
        loan.Loan,
        contract.AveragePremiumRateLoanDisplayer,
        contract.DisplayLoanAveragePremiumValues,
        module='loan_apr', type_='model')

    Pool.register(
        contract.DisplayLoanAveragePremium,
        module='loan_apr', type_='wizard')
