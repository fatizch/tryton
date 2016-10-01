# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'Clause',
    ]


class Clause:
    __name__ = 'clause'

    products = fields.Many2Many('offered.product-clause', 'clause', 'product',
        'Products')

    @classmethod
    def _export_skips(cls):
        skips = super(Clause, cls)._export_skips()
        skips.add('products')
        return skips
