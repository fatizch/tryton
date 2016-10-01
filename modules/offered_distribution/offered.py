# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'Product',
    ]


class Product:
    __name__ = 'offered.product'

    com_products = fields.One2Many('distribution.commercial_product',
        'product', 'Commercial Products', delete_missing=True)

    @classmethod
    def copy(cls, products, default=None):
        default = {} if default is None else default.copy()
        default.setdefault('com_products', None)
        return super(Product, cls).copy(products, default=default)

    @classmethod
    def _export_skips(cls):
        result = super(Product, cls)._export_skips()
        result.add('com_products')
        return result
