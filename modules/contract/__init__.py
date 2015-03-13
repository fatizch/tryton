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
from .batch import *


def register():
    Pool.register(
        Configuration,
        Product,
        ContractSubStatus,
        Contract,
        ActivationHistory,
        ContractOption,
        ContractAddress,
        ContractEndDateTerminationBatch,
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
        ContactType,
        ContractContact,
        SynthesisMenuContrat,
        SynthesisMenu,
        ContractActivateConfirm,
        ContractSelectDeclineReason,
        ContractStopSelectContracts,
        ContractSelectHoldReason,
        module='contract', type_='model')
    Pool.register(
        OptionSubscription,
        OptionSubscriptionWizardLauncher,
        SynthesisMenuOpen,
        ContractEnd,
        ContractChangeStartDate,
        ContractActivate,
        ContractDecline,
        ContractStop,
        ContractHold,
        module='contract', type_='wizard')
