# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import product


def register():
    Pool.register(
        product.Product,
        product.Template,
        product.Uom,
        product.Category,
        product.ProductCostPrice,
        product.ProductListPrice,
        product.ProductCostPriceMethod,
        product.CategoryAccount,
        module='product_cog', type_='model')
