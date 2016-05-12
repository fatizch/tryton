from trytond.pool import Pool
from .benefit import *
from .claim import *
from .rule_engine import *
from .invoice import *
from .wizard import *
from .configuration import *
from .event import *


def register():
    Pool.register(
        Benefit,
        BenefitRule,
        Claim,
        ClaimService,
        Indemnification,
        IndemnificationTaxes,
        IndemnificationDetail,
        Invoice,
        InvoiceLine,
        ClaimInvoiceLineDetail,
        RuleEngine,
        RuleEngineRuntime,
        EventLog,
        ExtraDataValueDisplayer,
        ExtraDatasDisplayers,
        IndemnificationDefinition,
        IndemnificationCalculationResult,
        IndemnificationRegularization,
        IndemnificationAssistantView,
        IndemnificationValidateElement,
        IndemnificationControlElement,
        IndemnificationControlRule,
        Configuration,
        EventTypeAction,
        module='claim_indemnification', type_='model')
    Pool.register(
        FillExtraData,
        CreateIndemnification,
        IndemnificationAssistant,
        module='claim_indemnification', type_='wizard')
