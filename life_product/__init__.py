from trytond.pool import Pool
from .life_product import *


def register():
    Pool.register(
        # from life_product
        LifeCoverage,
        LifeProductDefinition,
        LifeEligibilityRule,
        module='life_product', type_='model')
