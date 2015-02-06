from trytond.pool import PoolMeta
from trytond.pyson import Id

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Fee',
    ]


class Fee:
    __name__ = 'account.fee'

    product = fields.Many2One('product.product', 'Product', required=True,
        domain=[
            ('type', '=', 'service'),
            ('default_uom', '=', Id('product', 'uom_unit')),
            ('template.type', '=', 'service'),
            ('template.default_uom', '=', Id('product', 'uom_unit')),
            ], ondelete='RESTRICT')

    def get_account_for_billing(self, line):
        return self.product.template.account_revenue_used
