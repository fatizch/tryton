from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Product',
    ]


class Product:
    __name__ = 'offered.product'

    com_products = fields.One2Many('distribution.commercial_product',
        'product', 'Commercial Products',
        states={'invisible': Eval('product_kind') != 'insurance'})

    @classmethod
    def copy(cls, products, default=None):
        default = {} if default is None else default.copy()
        default.setdefault('com_products', None)
        return super(Product, cls).copy(products, default=default)

    @classmethod
    def _export_force_recreate(cls):
        res = super(Product, cls)._export_force_recreate()
        res.remove('com_products')
        return res

    @classmethod
    def _export_skips(cls):
        result = super(Product, cls)._export_skips()
        result.add('com_products')
        return result
