from trytond.pool import Pool
from .health import *
from .party import *
from .contract import *


def register():
    Pool.register(
        Regime,
        InsuranceFund,
        PartyHealthComplement,
        CoveredElement,
        module='health_fr', type_='model')
