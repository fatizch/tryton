from trytond.pool import Pool
from .claim_process import *


def register():
    Pool.register(
        ClaimProcess,
        LossProcess,
        ProcessDesc,
        DeclarationProcessParameters,
        module='claim.declare.find_process', type_='model')

    Pool.register(
        DeclarationProcessFinder,
        module='claim.declare.find_process', type_='wizard')
