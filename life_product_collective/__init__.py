from trytond.pool import Pool
from .product import *
from .tranche import *
from .college import *
from .company import *


def register():
    Pool.register(
        GroupLifeCoverage,
        GroupPriceCalculator,
        GroupPricingData,
        TrancheCalculatorLine,
        College,
        CollegeTranche,
        Employee,
        TrancheCalculator,
        module='life_product_collective', type_='model')
