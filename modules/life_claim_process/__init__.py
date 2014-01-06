from trytond.pool import Pool
from .claim_process import *


def register():
    Pool.register(
        Loss,
        module='life_claim_process', type_='model')
