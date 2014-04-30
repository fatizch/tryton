from trytond.pool import Pool
from .clause import *
from .test_case import *
from .offered import *


def register():
    Pool.register(
        OptionDescription,
        Clause,
        OptionDescriptionBeneficiaryClauseRelation,
        TestCaseModel,
        module='offered_life_clause', type_='model')
