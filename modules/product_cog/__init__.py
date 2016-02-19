from trytond.pool import Pool
from .product import *


def register():
    Pool.register(
        Product,
        Template,
        Uom,
        Category,
        module='product_cog', type_='model')
