from trytond.pool import Pool
from .product import *
from .tranche import *


def register():
    Pool.register(
        GroupLifeCoverage,
        GroupPricingData,
        TrancheCalculator,
        TrancheCalculatorLine,
        module='life_product_collective', type_='model')
