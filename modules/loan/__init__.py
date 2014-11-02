from trytond.pool import Pool
from .offered import *
from .contract import *
from .rule_engine import *
from .loan import *
from .billing import *
from .party import *
from .wizard import *

from trytond.modules.cog_utils import expand_tree
LoanShareTreeExpansion = expand_tree('loan.share')


def register():
    Pool.register(
        PremiumDateConfiguration,
        Product,
        OptionDescription,
        RuleEngineRuntime,
        Loan,
        LoanIncrement,
        LoanPayment,
        LoanParty,
        Contract,
        ContractLoan,
        ContractOption,
        ExtraPremium,
        LoanShare,
        OptionsDisplayer,
        WizardOption,
        BillingPremium,
        LoanShareTreeExpansion,
        SynthesisMenuLoan,
        SynthesisMenu,
        InsuredOutstandingLoanBalanceView,
        InsuredOutstandingLoanBalanceLineView,
        InsuredOutstandingLoanBalanceSelectDate,
        module='loan', type_='model')
    Pool.register(
        OptionSubscription,
        OptionSubscriptionWizardLauncher,
        DisplayContractPremium,
        CreateExtraPremium,
        SynthesisMenuOpen,
        DisplayInsuredOutstandingLoanBalance,
        module='loan', type_='wizard')
