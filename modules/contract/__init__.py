from trytond.pool import Pool

from .contract import *
from .rule_engine import *
from .party import *
from .test_case import *
from .wizard import *
from .service import *


def register():
    Pool.register(
        # from contract
        StatusHistory,
        Contract,
        ContractOption,
        ContractAddress,
        # From Service
        ContractService,
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
        SynthesisMenu,
        SynthesisMenuContrat,
        module='contract', type_='model')
    Pool.register(
        OptionSubscription,
        SynthesisMenuOpen,
        module='contract', type_='wizard')
