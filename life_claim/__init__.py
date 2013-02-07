from trytond.pool import Pool
from .claim import *


def register():
    Pool.register(
        LifeClaimDeliveredService,
        module='life_claim', type_='model')
