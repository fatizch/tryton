# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import offered
import contract
import rule_engine
import party


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
