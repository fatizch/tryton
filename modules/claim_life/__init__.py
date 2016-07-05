from trytond.pool import Pool
from .claim import *
from .contract import *
from .test_case import *
from .benefit import *
from .wizard import *


def register():
    Pool.register(
        Benefit,
        LossDescription,
        ContractOption,
        ClaimService,
        ClaimServiceExtraDataRevision,
        Loss,
        TestCaseModel,
        IndemnificationValidateElement,
        IndemnificationControlElement,
        module='claim_life', type_='model')
