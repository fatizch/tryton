# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import rule_engine
from . import offered
from . import contract
from . import api


def register():
    Pool.register(
        rule_engine.RuleEngine,
        offered.OptionDescription,
        contract.Contract,
        contract.ContractOption,
        offered.OptionDescriptionEligibilityRule,
        module='offered_eligibility', type_='model')

    Pool.register(
        api.APIContract,
        module='offered_eligibility', type_='model', depends=['api'])
