from trytond.pool import Pool
from .life_product import *
from .tranche import *


def register():
    Pool.register(
        # from life_product
        LifeCoverage,
        LifeProductDefinition,
        LifeEligibilityRule,
        Tranche,
        TrancheVersion,
        TrancheCalculator,
        TrancheCalculatorLine,
        module='life_product', type_='model')
