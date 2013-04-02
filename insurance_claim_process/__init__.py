from trytond.pool import Pool
from .claim_process import *


def register():
    Pool.register(
        ClaimProcess,
        LossProcess,
        ProcessDesc,
        DeliveredServiceProcess,
        DeclarationProcessParameters,
        module='insurance_claim_process', type_='model')

    Pool.register(
        DeclarationProcessFinder,
        module='insurance_claim_process', type_='wizard')
