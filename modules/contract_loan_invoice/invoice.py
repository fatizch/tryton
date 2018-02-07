# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'InvoiceLineDetail',
    'InvoiceLine'
    ]


class InvoiceLineDetail:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.line.detail'

    loan = fields.Many2One('loan', 'Loan', readonly=True, ondelete='RESTRICT')

    @classmethod
    def new_detail_from_premium(cls, premium=None):
        new_detail = super(InvoiceLineDetail, cls).new_detail_from_premium(
            premium)
        if premium:
            new_detail.loan = getattr(premium, 'loan', None)
        return new_detail


class InvoiceLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.line'

    loan = fields.Function(
        fields.Many2One('loan', 'Loan'),
        'get_loan')

    def get_loan(self, name=None):
        if self.detail and self.detail.premium:
            loan = getattr(self.detail.premium, 'loan', None)
            if loan:
                return loan.id
