# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import product


def register():
    Pool.register(
        product.Product,
        product.Template,
        product.Uom,
        product.Category,
        module='product_cog', type_='model')
