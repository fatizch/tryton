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
        DisplayLoanAveragePremiumValues,
        LoanAveragePremiumRule,
        FeeRule,
        Product,
        module='contract_loan_invoice', type_='model')

    Pool.register(
        DisplayLoanAveragePremium,
        module='contract_loan_invoice', type_='wizard')
