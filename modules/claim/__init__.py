from trytond.pool import Pool
from .claim import *
from .product import *
from .contract import *
from .rule_engine import *
from .party import *
from .test_case import *


def register():
    Pool.register(
        # from claim
        ClaimCoverage,
        Claim,
        Loss,
        ClaimDeliveredService,
        Indemnification,
        IndemnificationDetail,
        # from product
        Document,
        DocumentRequest,
        RequestFinder,
        ContactHistory,
        # from contract
        ClaimHistory,
        ClaimContract,
        ClaimOption,
        IndemnificationDisplayer,
        IndemnificationSelection,
        #From Rule Engine
        OfferedContext,
        ClaimContext,
        # From Party,
        Party,
        # from test_case
        TestCaseModel,
        module='claim', type_='model')

    Pool.register(
        IndemnificationValidation,
        module='claim', type_='wizard')
