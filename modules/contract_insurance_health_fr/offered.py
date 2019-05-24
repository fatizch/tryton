# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.coog_core import fields, coog_string
from trytond.pool import PoolMeta


__all__ = [
    'Product',
    ]


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    print_madelin_reports = fields.Boolean('Print Madelin Reports',
        help='If set, the batch will retrieve associated contracts each '
        'new civil year for the Madelin reports generation')

    def get_documentation_structure(self):
        doc = super(Product, self).get_documentation_structure()
        doc['parameters'].append(
            coog_string.doc_for_field(self, 'print_madelin_reports'))
        return doc
