from trytond.pool import Pool
from .clause import *
from .clause_rule import *
from .test_case import *


def register():
    Pool.register(
        Clause,
        ClauseRule,
        TestCaseModel,
        module='clause_life', type_='model')
