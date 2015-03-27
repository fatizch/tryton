from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Product',
    ]


class Product:
    __name__ = 'offered.product'

    payment_journal = fields.Many2One('account.payment.journal',
        'Payment Journal', domain=[('process_method', '!=', 'manual')],
        ondelete='RESTRICT',
        help='If no journal defined the global configuration will be used')
