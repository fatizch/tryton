# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .rule_engine import *
from .offered import *
from .contract import *


def register():
    Pool.register(
        RuleEngine,
        RuleEngineRuntime,
        OptionDescription,
        CoverageAmountRule,
        Contract,
        CoveredElement,
        ContractOption,
        ContractOptionVersion,
        module='contract_coverage_amount', type_='model')
