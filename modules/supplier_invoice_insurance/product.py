# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'Product',
]


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'product.product'

    capped_amount = fields.Numeric('Capped amount')
