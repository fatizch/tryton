from trytond.pool import Pool
from .product import *


def register():
    Pool.register(
        GroupLifeCoverage,
        module='life_product_collective', type_='model')
