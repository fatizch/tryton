# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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
from .event import *
from .notification import *
import party


def register():
    Pool.register(
        Product,
        ContractSubStatus,
        Configuration,
        Contract,
        ActivationHistory,
        ContractOption,
        ContractOptionVersion,
        ContractEndDateTerminationBatch,
        ContractExtraDataRevision,
        ContractSelectStartDate,
        ContractService,
        RuleEngineRuntime,
        Party,
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
        ContractReactivateCheck,
        ContractNotification,
        EventTypeAction,
        EventLog,
        ContractDeclineInactiveQuotes,
        module='contract', type_='model')
    Pool.register(
        OptionSubscription,
        SynthesisMenuOpen,
        ContractChangeStartDate,
        ContractActivate,
        ContractDecline,
        ContractStop,
        ContractHold,
        ContractReactivate,
        RelatedAttachments,
        party.PartyReplace,
        module='contract', type_='wizard')
