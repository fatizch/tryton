from trytond.pool import Pool
from .product import *


def register():
    Pool.register(
        # From product
        Coverage,
        module='property_product', type_='model')
