from trytond.pool import Pool
from .claim import *
from .contract import *
from .test_case import *


def register():
    Pool.register(
        # from life_contract
        ContractOption,
        DeliveredService,
        # from life_claim
        Loss,
        ClaimIndemnification,
        # from test_module
        TestCaseModel,
        module='claim_life', type_='model')
