from trytond.pool import Pool
from .offered import *
from .contract import *
from .rule_engine import *
from .loan import *
from .loan_creation_wizard import *
from .billing import *
from .party import *
from .wizard import *

from trytond.modules.cog_utils import expand_tree
LoanShareTreeExpansion = expand_tree('loan.share')


def register():
    Pool.register(
        Product,
        OptionDescription,
        PremiumRule,
        RuleEngineRuntime,
        Loan,
        LoanIncrement,
        LoanPayment,
        LoanParty,
        Contract,
        ContractOption,
        ExtraPremium,
        LoanShare,
        OptionsDisplayer,
        WizardOption,
        BillingPremium,
        LoanShareTreeExpansion,
        Party,
        Insurer,
        SynthesisMenuLoan,
        SynthesisMenu,
        module='loan', type_='model')
    Pool.register(
        LoanCreate,
        OptionSubscription,
        OptionSubscriptionWizardLauncher,
        DisplayContractPremium,
        CreateExtraPremium,
        SynthesisMenuOpen,
        module='loan', type_='wizard')
