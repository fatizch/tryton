# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'Product',
    ]


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    paybox_payment_journal = fields.Many2One('account.payment.journal',
        'Paybox Payment Journal', domain=[('process_method', '=', 'paybox')],
        ondelete='RESTRICT', help='Paybox payment journal which will be used if'
        ' a product\'s billing mode process method is Paybox')
