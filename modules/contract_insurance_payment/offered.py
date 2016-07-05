from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

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


class BillingMode:
    __name__ = 'offered.billing_mode'

    failure_billing_mode = fields.Many2One('offered.billing_mode',
        'Failure Billing Mode', ondelete='RESTRICT',
        domain=[('direct_debit', '=', False)],
        states={'invisible': ~Eval('direct_debit')},
        depends=['direct_debit'])
