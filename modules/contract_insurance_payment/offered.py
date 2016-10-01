# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'BillingMode',
    ]


class Product:
    __name__ = 'offered.product'

    payment_journal = fields.Many2One('account.payment.journal',
        'Payment Journal', domain=[('process_method', '!=', 'manual')],
        ondelete='RESTRICT',
        help='If no journal defined the global configuration will be used')

    @classmethod
    def _export_light(cls):
        return super(Product, cls)._export_light() | {'payment_journal'}


class BillingMode:
    __name__ = 'offered.billing_mode'

    failure_billing_mode = fields.Many2One('offered.billing_mode',
        'Failure Billing Mode', ondelete='RESTRICT',
        domain=[('direct_debit', '=', False)],
        states={'invisible': ~Eval('direct_debit')},
        depends=['direct_debit'])
