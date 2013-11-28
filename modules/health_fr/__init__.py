from trytond.pool import Pool
from .health import *
from .party import *
from .contract import *
from .rule_engine import *
from .test_case import *


def register():
    Pool.register(
        Regime,
        InsuranceFund,
        PartyHealthComplement,
        CoveredElement,
        #Rule Engine Context
        HealthContext,
        # from test_case
        TestCaseModel,
        module='health_fr', type_='model')
