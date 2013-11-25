from trytond.pool import Pool
from .life_claim import *
from .life_contract import *
from .test_case import *


def register():
    Pool.register(
        # from life_contract
        LifeOption,
        LifeClaimDeliveredService,
        # from life_claim
        LifeClaim,
        LifeLoss,
        LifeIndemnification,
        # from test_module
        TestCaseModel,
        module='life_claim', type_='model')
