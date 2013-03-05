from trytond.pool import Pool
from .life_claim import *


def register():
    Pool.register(
        LifeClaimDeliveredService,
        module='life_claim', type_='model')
