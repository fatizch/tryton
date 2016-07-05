from trytond.pool import Pool
from .claim import *
from .offered import *
from .contract import *
from .rule_engine import *
from .party import *
from .test_case import *
from .report_engine import *
from .benefit import *
from .wizard import *
from .event import *
from .configuration import *


def register():
    Pool.register(
        EventDescription,
        LossDescription,
        Benefit,
        EventDescriptionLossDescriptionRelation,
        BenefitLossDescriptionRelation,
        OptionDescriptionBenefitRelation,
        LossDescriptionExtraDataRelation,
        BenefitExtraDataRelation,
        ClaimSubStatus,
        Claim,
        Loss,
        ClaimService,
        ClaimServiceExtraDataRevision,
        Contract,
        Option,
        RuleEngineRuntime,
        Party,
        PartyInteraction,
        OptionDescription,
        TestCaseModel,
        BenefitToDeliver,
        SelectBenefits,
        SynthesisMenuClaim,
        SynthesisMenu,
        ReportTemplate,
        EventLog,
        Configuration,
        ClaimCloseReasonView,
        module='claim', type_='model')
    Pool.register(
        CloseClaim,
        DeliverBenefits,
        SynthesisMenuOpen,
        module='claim', type_='wizard')
