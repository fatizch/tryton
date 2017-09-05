# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import rule_engine
import offered
import contract


def register():
    Pool.register(
        rule_engine.RuleEngine,
        rule_engine.RuleEngineRuntime,
        offered.OptionDescription,
        offered.CoverageAmountRule,
        contract.Contract,
        contract.ContractOption,
        contract.ContractOptionVersion,
        module='contract_coverage_amount_revaluation', type_='model')
