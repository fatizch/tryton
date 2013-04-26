from trytond.pool import Pool
from .claim_process import *


def register():
    Pool.register(
        LifeLossProcess,
        module='life_claim_process', type_='model')
