from trytond.pool import Pool
from .product import *


def register():
    Pool.register(
        GroupHealthCoverage,
        module='health_product_collective', type_='model')
