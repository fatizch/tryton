# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import offered
from . import contract
from . import rule_engine
from . import party
from . import api


def register():
    Pool.register(
        offered.Product,
        offered.OptionDescription,
        party.Party,
        party.HealthPartyComplement,
        contract.Contract,
        contract.Option,
        contract.CoveredElement,
        rule_engine.RuleEngineRuntime,
        module='health', type_='model')
    Pool.register(
        party.PartyReplace,
        module='health', type_='wizard')

    Pool.register(
        api.APIProduct,
        api.APIParty,
        api.APIContract,
        module='health', type_='model', depends=['api'])
