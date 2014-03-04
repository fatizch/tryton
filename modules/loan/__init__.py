from trytond.pool import Pool
from .offered import *
from .contract import *
from .rule_engine import *
from .loan import *
from .loan_creation_wizard import *
from .billing import *

from trytond.modules.cog_utils import expand_tree
LoanShareTreeExpansion = expand_tree('loan.share')


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
        LoanShare,
        LoanIncrement,
        LoanPayment,
        # From Billing
        BillingPremium,
        #From loan_creation_wizard
        LoanSharePropagateParameters,
        LoanShareTreeExpansion,
        module='loan', type_='model')
    Pool.register(
        LoanCreate,
        LoanSharePropagate,
        module='loan', type_='wizard')
