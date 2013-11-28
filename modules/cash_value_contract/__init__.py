from trytond.pool import Pool
from .account import *
from .contract import *
from .product import *
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
        # From file product
        CoveredDataRuleSet,
        # From file wizard
        SelectDate,
        CashSurrenderParameters,
        # From file test_case
        TestCaseModel,
        module='cash_value_contract', type_='model')

    Pool.register(
        # From file wizard
        CollectionToCashValue,
        CashValueUpdate,
        CashSurrenderWizard,
        module='cash_value_contract', type_='wizard')
