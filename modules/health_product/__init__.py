from trytond.pool import Pool
from .product import *


def register():
    Pool.register(
        HealthCoverage,
        module='health_product', type_='model')
