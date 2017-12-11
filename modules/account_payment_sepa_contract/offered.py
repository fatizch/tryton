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

    sepa_mandate_sequence = fields.Many2One('ir.sequence',
        "SEPA Mandate Sequence", domain=[
            ('code', '=', 'account.payment.sepa.mandate')],
        ondelete='RESTRICT')
