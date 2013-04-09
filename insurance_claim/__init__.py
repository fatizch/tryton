from trytond.pool import Pool
from .claim import *
from .product import *
from .contract import *
from .claim_rule_sets import *


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
        ClaimContext,
        module='insurance_claim', type_='model')
