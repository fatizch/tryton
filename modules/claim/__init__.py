from trytond.pool import Pool
from .claim import *
from .offered import *
from .contract import *
from .rule_engine import *
from .party import *
from .test_case import *
from .document import *


def register():
    Pool.register(
        # From Claim
        Claim,
        Loss,
        ClaimService,
        # From Document
        Document,
        DocumentRequest,
        RequestFinder,
        # from contract
        Contract,
        Option,
        # From Rule Engine
        RuleEngineRuntime,
        # From Party,
        Party,
        PartyInteraction,
        # From Offered
        OptionDescription,
        # from test_case
        TestCaseModel,
        module='claim', type_='model')
