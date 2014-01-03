from trytond.pool import Pool

from .contract import *
from .rule_engine import *
from .party import *
from .test_case import *
from .wizard import *
from .clause import *
from .service import *
from .document import *


def register():
    Pool.register(
        # from contract
        StatusHistory,
        Contract,
        ContractOption,
        ContractAddress,
        # From Service
        ContractService,
        # From Clause
        ContractClause,
        # From Document
        DocumentTemplate,
        #From Rule Engine
        RuleEngineRuntime,
        # from party
        Party,
        PartyInteraction,
        # from test_case
        TestCaseModel,
        #From Wizard
        OptionsDisplayer,
        WizardOption,
        module='contract', type_='model')
    Pool.register(
        OptionSubscription,
        module='contract', type_='wizard')
