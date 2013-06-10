from trytond.pool import Pool
from .life_product import *
from .tranche import *


def register():
    Pool.register(
        LifeItemDescriptor,
        LifeCoverage,
        LifeEligibilityRule,
        Tranche,
        TrancheVersion,
        LifeLossDesc,
        LifeBenefit,
        LifeBenefitRule,
        module='life_product', type_='model')
