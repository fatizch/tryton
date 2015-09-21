from trytond.model import fields
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Configuration',
    ]


class Configuration:
    __name__ = 'account.configuration'

    default_customer_payment_term = fields.Many2One(
        'account.invoice.payment_term', string='Default Customer Payment Term',
        ondelete='SET NULL')
