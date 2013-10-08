from trytond.pool import Pool
from .loan import *


def register():
    Pool.register(
        LoanContract,
        LoanOption,
        Loan,
        LoanShare,
        LoanCoveredData,
        LoanCoveredElement,
        LoanCoveredDataLoanShareRelation,
        LoanIncrement,
        LoanPayment,
        LoanParameters,
        LoanIncrementsDisplayer,
        AmortizationTableDisplayer,
        module='loan_contract', type_='model')
    Pool.register(
        LoanCreation,
        module='loan_contract', type_='wizard')
