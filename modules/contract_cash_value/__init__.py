# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .account import *
from .contract import *
from .rule_engine import *
from .wizard import *
from .test_case import *


def register():
    Pool.register(
        # From file account
        Configuration,
        MoveLine,
        # From file contract
        CashValueCollection,
        Contract,
        # From file rule_engine
        CoveredDataRuleSet,
        # From file wizard
        SelectDate,
        CashSurrenderParameters,
        # From file test_case
        TestCaseModel,
        module='contract_cash_value', type_='model')

    Pool.register(
        # From file wizard
        CollectionToCashValue,
        CashValueUpdate,
        CashSurrenderWizard,
        module='contract_cash_value', type_='wizard')
