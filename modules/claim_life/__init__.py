# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .claim import *
from .contract import *
from .test_case import *
from .benefit import *
from .wizard import *
from .rule_engine import *


def register():
    Pool.register(
        Benefit,
        LossDescription,
        ContractOption,
        ClaimService,
        ClaimServiceExtraDataRevision,
        Claim,
        Loss,
        RuleEngineRuntime,
        TestCaseModel,
        IndemnificationValidateElement,
        IndemnificationControlElement,
        module='claim_life', type_='model')