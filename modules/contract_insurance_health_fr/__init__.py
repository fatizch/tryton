from trytond.pool import Pool
from .health import *
from .party import *
from .contract import *
from .rule_engine import *
from .test_case import *


def register():
    Pool.register(
        Party,
        PartyRelation,
        HealthCareSystem,
        InsuranceFund,
        HealthPartyComplement,
        CoveredElement,
        RuleEngineRuntime,
        TestCaseModel,
        module='contract_insurance_health_fr', type_='model')
