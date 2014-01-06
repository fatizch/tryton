from trytond.pool import Pool
from .life_product import *
from .salary_range import *
from .test_case import *
from .rule_engine import *


def register():
    Pool.register(
        # from life_product
        OptionDescription,
        EligibilityRule,
        # From rule_engine
        RuleEngineRuntime,
        # from salary_range
        SalaryRange,
        SalaryRangeVersion,
        # from test_case
        TestCaseModel,
        module='life_product', type_='model')
