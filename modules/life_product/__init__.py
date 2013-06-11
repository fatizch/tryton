from trytond.pool import Pool
from .life_product import *
from .tranche import *


def register():
    Pool.register(
        LifeItemDescriptor,
        LifeCoverage,
        LifeProductDefinition,
        LifeEligibilityRule,
        Tranche,
        TrancheVersion,
        LifeLossDesc,
        LifeBenefit,
        LifeBenefitRule,
        CoveredDataContext,
        module='life_product', type_='model')
