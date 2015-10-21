from trytond.pool import Pool
from .rule_engine import *
from .offered import *
from .contract import *


def register():
    Pool.register(
        RuleEngine,
        OptionDescription,
        CoverageAmountRule,
        Contract,
        ContractOption,
        module='contract_coverage_amount_revaluation', type_='model')
