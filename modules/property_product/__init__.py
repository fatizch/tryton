from trytond.pool import Pool
from .product import *


def register():
    Pool.register(
        # From product
        OptionDescription,
        module='property_product', type_='model')
