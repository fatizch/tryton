from trytond.pool import Pool
from .offered import *
from .contract import *
from .rule_engine import *
from .loan import *
from .loan_creation_wizard import *
from .billing import *


def register():
    Pool.register(
        # From offered
        Product,
        OptionDescription,
        # From rule_engine
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
