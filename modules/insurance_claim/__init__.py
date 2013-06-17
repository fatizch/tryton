from trytond.pool import Pool
from .claim import *
from .product import *
from .contract import *
from .rule_engine import *


def register():
    Pool.register(
        ClaimCoverage,
        Claim,
        Loss,
        ClaimDeliveredService,
        Indemnification,
        IndemnificationDetail,
        Document,
        DocumentRequest,
        RequestFinder,
        ContactHistory,
        ClaimHistory,
        ClaimContract,
        ClaimOption,
        IndemnificationDisplayer,
        IndemnificationSelection,
        #From Rule Engine
        OfferedContext,
        ClaimContext,
        module='insurance_claim', type_='model')

    Pool.register(
        IndemnificationValidation,
        module='insurance_claim', type_='wizard')
