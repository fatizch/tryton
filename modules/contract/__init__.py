from trytond.pool import Pool

from .contract import *
from .rule_engine import *
from .party import *
from .test_case import *
from .wizard import *
from .service import *
from .contact_type import *
from .configuration import *
from .offered import *


def register():
    Pool.register(
        Configuration,
        Product,
        # from contract
        Contract,
        ActivationHistory,
        ContractOption,
        ContractAddress,
        ContractSelectEndDate,
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
        ContactType,
        ContractContact,
        module='contract', type_='model')
    Pool.register(
        OptionSubscription,
        OptionSubscriptionWizardLauncher,
        SynthesisMenuOpen,
        ContractEnd,
        module='contract', type_='wizard')
