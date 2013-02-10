from trytond.pool import Pool
from .claim import *
from .product import *


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
        module='insurance_claim', type_='model')
