from trytond.pool import Pool
from .life_product import *
from .tranche import *
from .test_case import *


def register():
    Pool.register(
        # from life_product
        LifeItemDescriptor,
        LifeCoverage,
        LifeEligibilityRule,
        LifeLossDesc,
        LifeBenefit,
        LifeBenefitRule,
        CoveredDataContext,
        # from tranche
        Tranche,
        TrancheVersion,
        # from test_case
        TestCaseModel,
        module='life_product', type_='model')
