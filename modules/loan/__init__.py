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
        CoveredData,
        ExtraPremium,
        # From Loan
        Loan,
        ContractLoanRelation,
        LoanShare,
        LoanIncrement,
        LoanPayment,
        # From Billing
        BillingPremium,
        #From loan_creation_wizard
        LoanSharePropagateParameters,
        module='loan', type_='model')
    Pool.register(
        LoanCreate,
        LoanSharePropagate,
        module='loan', type_='wizard')
