from trytond.pool import Pool
from .clause_rule import *
from .offered import *
from .test_case import *


def register():
    Pool.register(
        ClauseRule,
        RuleClauseRelation,
        OfferedMixin,
        Product,
        OptionDescription,
        TestCaseModel,
        module='clause_insurance', type_='model')
