# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import account
import contract
import rule_engine
import wizard
import test_case


def register():
    Pool.register(
        account.Configuration,
        account.MoveLine,
        contract.CashValueCollection,
        contract.Contract,
        rule_engine.CoveredDataRuleSet,
        wizard.SelectDate,
        wizard.CashSurrenderParameters,
        test_case.TestCaseModel,
        module='contract_cash_value', type_='model')

    Pool.register(
        wizard.CollectionToCashValue,
        wizard.CashValueUpdate,
        wizard.CashSurrenderWizard,
        module='contract_cash_value', type_='wizard')
