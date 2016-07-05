# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .product import *


def register():
    Pool.register(
        Product,
        Template,
        Uom,
        Category,
        module='product_cog', type_='model')
