# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields, coog_string


__all__ = [
    'Product',
    ]


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    processes = fields.Many2Many('process-offered.product',
        'product', 'process', 'Processes',
        help='Processes available for this product')

    @classmethod
    def _export_light(cls):
        return super(Product, cls)._export_light() | {'processes'}

    def get_documentation_structure(self):
        doc = super(Product, self).get_documentation_structure()
        doc['parameters'].append(
            coog_string.doc_for_field(self, 'processes'))
        return doc
