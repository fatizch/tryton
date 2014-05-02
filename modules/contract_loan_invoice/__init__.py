from trytond.pool import Pool
from .contract import *


def register():
    Pool.register(
        ContractOption,
        LoanShare,
        Premium,
        Contract,
        Loan,
        DisplayLoanMeanPremiumValues,
        module='contract_loan_invoice', type_='model')

    Pool.register(
        DisplayLoanMeanPremium,
        module='contract_loan_invoice', type_='wizard')
