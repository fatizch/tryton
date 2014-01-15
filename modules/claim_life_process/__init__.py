from trytond.pool import Pool
from .claim import *


def register():
    Pool.register(
        # From claim
        Loss,
        module='claim_life_process', type_='model')
