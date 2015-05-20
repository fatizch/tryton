from trytond.pool import Pool
from .rule_engine import *
from .offered import *
from .contract import *


def register():
    Pool.register(
        RuleEngine,
        OptionDescription,
        Contract,
        ContractOption,
        OptionDescriptionEligibilityRule,
        module='offered_eligibility', type_='model')
