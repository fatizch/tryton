from trytond.model import fields
from trytond.pyson import Eval, Bool
from trytond.pool import PoolMeta

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
