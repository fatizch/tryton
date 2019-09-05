# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from sql.conditionals import Coalesce

from trytond.pool import PoolMeta


__all__ = [
    'CreateInvoiceContractBatch',
    ]


class CreateInvoiceContractBatch(metaclass=PoolMeta):
    __name__ = 'contract.invoice.create'

    @classmethod
    def _select_ids_where_clause(cls, tables, treatment_date):
        min_date = datetime.date.min
        return super(CreateInvoiceContractBatch, cls)._select_ids_where_clause(
            tables, treatment_date) & (Coalesce(
                tables['contract'].invoicing_end_date,
                min_date) <= treatment_date)
