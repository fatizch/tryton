from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Product',
]


class Product:
    __name__ = 'product.product'

    capped_amount = fields.Numeric('Capped amount')
