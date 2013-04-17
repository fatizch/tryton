from trytond.pool import Pool
from .life_claim import *
from .life_contract import *


def register():
    Pool.register(
        LifeOption,
        LifeClaim,
        LifeLoss,
        LifeClaimDeliveredService,
        module='life_claim', type_='model')
