from trytond.pool import Pool

from .offered import *
from .party import *
from .contract import *
from .rule_engine import *


def register():
    Pool.register(
        # From offered
        Product,
        OptionDescription,
        Party,
        HealthPartyComplement,
        Contract,
        Option,
        CoveredElement,
        RuleEngineRuntime,
        module='health', type_='model')
