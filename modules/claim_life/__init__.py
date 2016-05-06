from trytond.pool import Pool
from .claim import *
from .contract import *
from .test_case import *
from .benefit import *

def register():
    Pool.register(
        Benefit,
        LossDescription,
        ContractOption,
        ClaimService,
        ClaimServiceExtraDataRevision,
        Loss,
        TestCaseModel,
        module='claim_life', type_='model')
