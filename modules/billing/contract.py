from trytond.pool import PoolMeta

from trytond.modules.coop_utils import fields

__metaclass__ = PoolMeta

__all__ = [
    'Contract',
]


class Contract():
    'Contract'

    __name__ = 'contract'

    manual_billing = fields.Boolean('Manual Billing')
