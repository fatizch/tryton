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
        module='loan_contract', type_='model')
