# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import contract
from . import offered
from . import rule_engine


def register():
    Pool.register(
        contract.Contract,
        contract.ContractOption,
        offered.OptionDescription,
        rule_engine.RuleEngineRuntime,
        module='contract_insurance_planned_event', type_='model')
