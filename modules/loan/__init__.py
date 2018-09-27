# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import offered
import contract
import rule_engine
import loan
import party
import wizard
import extra_data
import commission

from trytond.modules.coog_core import model
LoanShareTreeExpansion = model.expand_tree('loan.share')


def register():
    Pool.register(
        offered.ProductConfiguration,
        offered.Product,
        offered.OptionDescription,
        rule_engine.RuleEngineRuntime,
        loan.Loan,
        loan.LoanPayment,
        loan.LoanIncrement,
        contract.Contract,
        contract.ContractLoan,
        contract.ContractOption,
        contract.ExtraPremium,
        contract.LoanShare,
        extra_data.ExtraData,
        contract.OptionsDisplayer,
        contract.WizardOption,
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
        commission.SimulateCommissionsParameters,
        module='loan', type_='model',
        depends=['commission_insurance'])
    Pool.register(
        contract.OptionSubscription,
        wizard.CreateExtraPremium,
        party.SynthesisMenuOpen,
        party.DisplayInsuredOutstandingLoanBalance,
        party.PartyReplace,
        module='loan', type_='wizard')
    Pool.register(
        contract.DisplayContractPremium,
        module='loan', type_='wizard',
        depends=['premium'])
