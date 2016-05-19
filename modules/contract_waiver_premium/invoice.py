from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields

__all__ = [
    'InvoiceLineDetail',
    ]
__metaclass__ = PoolMeta


class InvoiceLineDetail:
    __name__ = 'account.invoice.line.detail'

    waiver = fields.Many2One('contract.waiver_premium', 'Waiver Of Premium',
        select=True, ondelete='RESTRICT', readonly=True)

    @classmethod
    def get_possible_parent_field(cls):
        return super(InvoiceLineDetail, cls).get_possible_parent_field() | {
            'waiver'}
