from trytond.pool import Pool
from .contract import *
from .offered import *


def register():
    Pool.register(
        ContractOption,
        LoanShare,
        Premium,
        Contract,
        Loan,
        DisplayLoanMeanPremiumValues,
        LoanMeanRateRule,
        FeeRule,
        Product,
        module='contract_loan_invoice', type_='model')

    Pool.register(
        DisplayLoanMeanPremium,
        module='contract_loan_invoice', type_='wizard')
