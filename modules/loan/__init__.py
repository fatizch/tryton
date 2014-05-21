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
        PremiumRule,
        # From rule_engine
        RuleEngineRuntime,
        # From Loan
        Loan,
        LoanIncrement,
        LoanPayment,
        LoanParty,
        # From Contract
        Contract,
        ContractOption,
        ExtraPremium,
        LoanShare,
        OptionsDisplayer,
        WizardOption,
        # From Billing
        BillingPremium,
        #From loan_creation_wizard
        LoanShareTreeExpansion,
        module='loan', type_='model')
    Pool.register(
        LoanCreate,
        OptionSubscription,
        OptionSubscriptionWizardLauncher,
        DisplayContractPremium,
        module='loan', type_='wizard')
