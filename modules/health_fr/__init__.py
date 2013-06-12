from trytond.pool import Pool
from .health import *
from .party import *
from .contract import *
from .rule_engine import *


def register():
    Pool.register(
        Regime,
        InsuranceFund,
        PartyHealthComplement,
        CoveredElement,
        #Rule Engine Context
        HealthContext,
        module='health_fr', type_='model')
