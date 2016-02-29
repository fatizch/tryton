from trytond.pool import Pool
from .claim import *
from .offered import *
from .contract import *
from .rule_engine import *
from .party import *
from .test_case import *
from .document import *
from .report_engine import *


def register():
    Pool.register(
        Claim,
        Loss,
        ClaimService,
        DocumentRequest,
        RequestFinder,
        Contract,
        Option,
        RuleEngineRuntime,
        Party,
        PartyInteraction,
        OptionDescription,
        TestCaseModel,
        SynthesisMenuClaim,
        SynthesisMenu,
        ReportTemplate,
        module='claim', type_='model')
    Pool.register(
        SynthesisMenuOpen,
        module='claim', type_='wizard')
