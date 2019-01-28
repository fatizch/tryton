# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal
from trytond.pool import PoolMeta

__all__ = [
    'InvoiceSlipConfiguration',
    ]


class InvoiceSlipConfiguration(metaclass=PoolMeta):
    __name__ = 'account.invoice.slip.configuration'

    @classmethod
    def _get_insurer_commission_where_clause(cls, tables, invoices_ids):
        commission = tables['commission']
        return super(InvoiceSlipConfiguration,
            cls)._get_insurer_commission_where_clause(tables,
            invoices_ids) & (commission.postponed != Literal(True))
