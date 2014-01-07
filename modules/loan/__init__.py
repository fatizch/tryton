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
        Product,
        OptionDescription,
        # From Rule Sets
        RuleEngineRuntime,
        # From Contract
        Contract,
        ContractOption,
        # From Loan
        Loan,
        LoanShare,
        CoveredData,
        CoveredDataLoanShareRelation,
        LoanIncrement,
        LoanPayment,
        # From Loan Create Wizard
        LoanCreateParameters,
        LoanCreateIncrement,
        LoanCreateAmortizationTable,
        # From Billing
        BillingPremium,
        module='loan', type_='model')
    Pool.register(
        LoanCreate,
        module='loan', type_='wizard')
