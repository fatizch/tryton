# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .benefit import *
from .claim import *
from .rule_engine import *
from .invoice import *
from .wizard import *
from .configuration import *
from .event import *
from .party import *
from .batch import *


def register():
    Pool.register(
        InsurerDelegation,
        Benefit,
        BenefitProduct,
        BenefitRule,
        Claim,
        Loss,
        ClaimService,
        Indemnification,
        IndemnificationDetail,
        Invoice,
        InvoiceLine,
        ClaimInvoiceLineDetail,
        RuleEngine,
        RuleEngineRuntime,
        EventLog,
        ExtraDataValueDisplayer,
        ExtraDatasDisplayers,
        SelectService,
        IndemnificationDefinition,
        IndemnificationCalculationResult,
        IndemnificationRegularisation,
        IndemnificationAssistantView,
        IndemnificationValidateElement,
        IndemnificationControlElement,
        IndemnificationControlRule,
        Configuration,
        EventTypeAction,
        CreateClaimIndemnificationBatch,
        module='claim_indemnification', type_='model')
    Pool.register(
        FillExtraData,
        CreateIndemnification,
        IndemnificationAssistant,
        module='claim_indemnification', type_='wizard')