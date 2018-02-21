# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields


__all__ = [
    'Product',
    ]


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'offered.product'

    processes = fields.Many2Many('process-offered.product',
        'product', 'process', 'Processes')

    @classmethod
    def _export_light(cls):
        return super(Product, cls)._export_light() | {'processes'}
