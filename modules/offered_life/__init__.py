from trytond.pool import Pool
from .offered import *
from .salary_range import *
from .test_case import *
from .rule_engine import *


def register():
    Pool.register(
        # from offered
        OptionDescription,
        EligibilityRule,
        # From rule_engine
        RuleEngineRuntime,
        # from salary_range
        SalaryRange,
        SalaryRangeVersion,
        # from test_case
        TestCaseModel,
        module='offered_life', type_='model')
