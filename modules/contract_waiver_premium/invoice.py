# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields

__all__ = [
    'InvoiceLineDetail',
    ]


class InvoiceLineDetail:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.line.detail'

    waiver = fields.Many2One('contract.waiver_premium', 'Waiver Of Premium',
        select=True, ondelete='RESTRICT', readonly=True)

    @classmethod
    def get_possible_parent_field(cls):
        return super(InvoiceLineDetail, cls).get_possible_parent_field() | {
            'waiver'}
