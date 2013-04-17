from trytond.pool import Pool
from .product import *


def register():
    Pool.register(
        Coverage,
        module='property_product', type_='model')
