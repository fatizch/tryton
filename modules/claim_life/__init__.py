from trytond.pool import Pool
from .claim import *
from .contract import *
from .test_case import *
from .benefit import *


def register():
    Pool.register(
        LossDescription,
        ContractOption,
        ClaimService,
        Loss,
        Claim,
        Indemnification,
        IndemnificationDetail,
        ClaimIndemnificationValidateDisplay,
        ClaimIndemnificationValidateSelect,
        TestCaseModel,
        module='claim_life', type_='model')
    Pool.register(
        ClaimIndemnificationValidate,
        module='claim_life', type_='wizard')
