from trytond.pool import Pool

from .contract import *
from .rule_engine import *
from .party import *
from .test_case import *
from .wizard import *


def register():
    Pool.register(
        # from contract
        StatusHistory,
        Contract,
        SubscribedCoverage,
        ContractClause,
        ContractAddress,
        DeliveredService,
        LetterModel,
        #From Rule Engine
        OfferedContext,
        ContractContext,
        # from party
        Party,
        ContactHistory,
        # from test_case
        TestCaseModel,
        #From Wizard
        OptionsDisplayer,
        WizardOption,
        module='contract', type_='model')
    Pool.register(
        OptionSubscription,
        module='contract', type_='wizard')
