# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pyson import Eval, Bool
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'Product',
    ]
__metaclass__ = PoolMeta


class Product:
    __name__ = 'offered.product'

    quote_number_sequence = fields.Property(fields.Many2One('ir.sequence',
            'Quote number sequence', domain=[
                ('code', '=', 'quote'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'required': Bool(Eval('context', {}).get('company')),
                'invisible': ~Eval('context', {}).get('company'),
                }))

    @classmethod
    def _export_light(cls):
        return (super(Product, cls)._export_light() |
            set(['quote_number_sequence']))
