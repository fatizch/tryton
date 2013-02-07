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
        module='life_product', type_='model')
