from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'InvoiceLineDetail',
    ]


class InvoiceLineDetail:
    __name__ = 'account.invoice.line.detail'

    loan = fields.Many2One('loan', 'Loan', readonly=True, ondelete='RESTRICT')

    @classmethod
    def new_detail_from_premium(cls, premium=None):
        new_detail = super(InvoiceLineDetail, cls).new_detail_from_premium(
            premium)
        if premium:
            new_detail.loan = getattr(premium, 'loan', None)
        return new_detail
