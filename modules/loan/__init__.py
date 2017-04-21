# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .offered import *
from .contract import *
from .rule_engine import *
from .loan import *
import party
from .wizard import *
from .extra_data import *

from trytond.modules.coog_core import expand_tree
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
        ExtraData,
        OptionsDisplayer,
        WizardOption,
        LoanShareTreeExpansion,
        party.Party,
        party.SynthesisMenuLoan,
        party.SynthesisMenu,
        party.InsuredOutstandingLoanBalanceView,
        party.InsuredOutstandingLoanBalanceLineView,
        party.InsuredOutstandingLoanBalanceSelectDate,
        party.Lender,
        module='loan', type_='model')
    Pool.register(
        OptionSubscription,
        DisplayContractPremium,
        CreateExtraPremium,
        party.SynthesisMenuOpen,
        party.DisplayInsuredOutstandingLoanBalance,
        party.PartyReplace,
        module='loan', type_='wizard')
