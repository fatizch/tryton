from trytond.pool import Pool
from .claim_process import *


def register():
    Pool.register(
        ClaimProcess,
        LossProcess,
        module='insurance_claim_process', type_='model')
