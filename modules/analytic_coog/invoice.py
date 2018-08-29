# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'InvoiceLine',
    ]


class InvoiceLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.line'

    def get_move_lines(self):
        lines = super(InvoiceLine, self).get_move_lines()
        if self.invoice.business_kind == 'broker_invoice':
            assert len(lines) == 1
        return lines

    @classmethod
    def default_analytic_accounts(cls):
        return []
