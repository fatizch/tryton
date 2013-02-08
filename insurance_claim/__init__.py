from trytond.pool import Pool
from .claim import *


def register():
    Pool.register(
        Claim,
        Loss,
        ClaimDeliveredService,
        Indemnification,
        IndemnificationDetail,
        Document,
        DocumentRequest,
        module='insurance_claim', type_='model')
