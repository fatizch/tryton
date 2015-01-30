from trytond.pool import Pool
from .product import *


def register():
    Pool.register(
        Product,
        Template,
        Uom,
        module='product_cog', type_='model')
