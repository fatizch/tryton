from trytond.pool import Pool
from .service import *
from .benefit import *


def register():
    Pool.register(
        ClaimService,
        BenefitRule,
        module='claim_credit', type_='model')
