# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .offered import *
from .party import *
from .contract import *
from .rule_engine import *
import party


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
    Pool.register(
        party.PartyReplace,
        module='health', type_='wizard')
