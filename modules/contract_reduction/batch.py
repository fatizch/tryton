# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null

from trytond.pool import PoolMeta


__all__ = [
    'CreateInvoiceContractBatch',
    ]


class CreateInvoiceContractBatch:
    __metaclass__ = PoolMeta
    __name__ = 'contract.invoice.create'

    @classmethod
    def _select_ids_where_clause(cls, tables, treatment_date):
        return super(CreateInvoiceContractBatch, cls)._select_ids_where_clause(
            tables, treatment_date) & (
            tables['contract'].reduction_date == Null)
