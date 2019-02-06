# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.coog_core import fields
from trytond.pool import PoolMeta


__all__ = [
    'Product',
    ]


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    print_madelin_reports = fields.Boolean('Print Madelin Reports',
        help='If set, the batch will retrieve associated contracts each '
        'new civil year for the Madelin reports generation')
