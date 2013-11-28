from trytond.pool import Pool
from .product import *
from .contract import *
from .rule_sets import *
from .loan import *
from .loan_creation_wizard import *
from .billing import *


def register():
    Pool.register(
        # From Product
        LoanProduct,
        LoanCoverage,
        # From Rule Sets
        LoanContext,
        # From Contract
        LoanContract,
        LoanOption,
        # From Loan
        Loan,
        LoanShare,
        LoanCoveredData,
        LoanCoveredDataLoanShareRelation,
        LoanIncrement,
        LoanPayment,
        # From Loan Creation Wizard
        LoanParameters,
        LoanIncrementsDisplayer,
        AmortizationTableDisplayer,
        # From Billing
        LoanPriceLine,
        module='loan', type_='model')
    Pool.register(
        LoanCreation,
        module='loan', type_='wizard')
