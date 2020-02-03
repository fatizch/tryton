# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import offered
from . import contract
from . import rule_engine
from . import loan
from . import party
from . import wizard
from . import extra_data
from . import commission
from . import api
from . import premium

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
        premium.ProductPremiumDate,
        module='loan', type_='model',
        depends=['premium'])
    Pool.register(
        contract.OptionSubscription,
        wizard.OptionSubscription,
        wizard.CreateExtraPremium,
        party.SynthesisMenuOpen,
        party.DisplayInsuredOutstandingLoanBalance,
        party.PartyReplace,
        module='loan', type_='wizard')
    Pool.register(
        contract.DisplayContractPremium,
        module='loan', type_='wizard',
        depends=['premium'])

    Pool.register(
        offered.OptionDescriptionEligibilityRule,
        module='loan', type_='model',
        depends=['offered_eligibility'])

    Pool.register(
        api.APIProduct,
        api.APIContract,
        module='loan', type_='model', depends=['api'])

    Pool.register(
        api.APIContractUnderwriting,
        module='loan', type_='model', depends=['api', 'contract_underwriting'])
