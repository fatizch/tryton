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
        ContractSubStatus,
        Contract,
        ActivationHistory,
        ContractOption,
        ContractAddress,
        ContractExtraDataRevision,
        ContractSelectEndDate,
        ContractSelectStartDate,
        ContractService,
        RuleEngineRuntime,
        Party,
        PartyInteraction,
        TestCaseModel,
        PackageSelection,
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
        ContractChangeStartDate,
        module='contract', type_='wizard')
