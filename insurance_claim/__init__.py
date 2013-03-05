from trytond.pool import Pool
from .claim import *
from .product import *
from .contract import *


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
        ClaimContract,
        module='insurance_claim', type_='model')
