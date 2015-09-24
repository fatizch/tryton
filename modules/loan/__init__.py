from trytond.pool import Pool
from .offered import *
from .contract import *
from .rule_engine import *
from .loan import *
from .party import *
from .wizard import *

from trytond.modules.cog_utils import expand_tree
LoanShareTreeExpansion = expand_tree('loan.share')


def register():
    Pool.register(
        Product,
        OptionDescription,
        RuleEngineRuntime,
        Loan,
        LoanIncrement,
        LoanPayment,
        Contract,
        ContractLoan,
        ContractOption,
        ExtraPremium,
        LoanShare,
        OptionsDisplayer,
        WizardOption,
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
        LoanIncrementCreate,
        module='loan', type_='wizard')
