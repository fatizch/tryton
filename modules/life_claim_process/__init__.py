from trytond.pool import Pool
from .claim import *


def register():
    Pool.register(
        # From claim
        Loss,
        module='life_claim_process', type_='model')
