# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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
import party


def register():
    Pool.register(
        ClosingReason,
        EventDescription,
        LossDescription,
        LossDescriptionClosingReason,
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
        OptionDescription,
        TestCaseModel,
        BenefitToDeliver,
        SelectBenefits,
        SynthesisMenuClaim,
        SynthesisMenu,
        InsurerDelegation,
        ReportTemplate,
        EventLog,
        Configuration,
        ClaimCloseReasonView,
        module='claim', type_='model')
    Pool.register(
        CloseClaim,
        DeliverBenefits,
        SynthesisMenuOpen,
        party.PartyReplace,
        module='claim', type_='wizard')
