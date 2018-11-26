# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.tools import grouped_slice
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields

__all__ = [
    'InvoiceLineDetail',
    'InvoiceLine'
    ]


class InvoiceLineDetail(metaclass=PoolMeta):
    __name__ = 'account.invoice.line.detail'

    loan = fields.Many2One('loan', 'Loan', readonly=True, ondelete='RESTRICT')

    @classmethod
    def new_detail_from_premium(cls, premium=None):
        new_detail = super(InvoiceLineDetail, cls).new_detail_from_premium(
            premium)
        if premium:
            new_detail.loan = getattr(premium, 'loan', None)
        return new_detail


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    loan = fields.Function(
        fields.Many2One('loan', 'Loan'),
        'getter_loan')

    @classmethod
    def getter_loan(cls, instances, name):
        pool = Pool()
        detail = pool.get('account.invoice.line.detail').__table__()
        premium = pool.get('contract.premium').__table__()

        result = {x.id: None for x in instances}
        cursor = Transaction().connection.cursor()
        query = detail.join(premium,
            condition=detail.premium == premium.id
            )

        for cur_slice in grouped_slice(instances):
            cursor.execute(*query.select(detail.invoice_line, premium.loan,
                    where=detail.invoice_line.in_([x.id for x in cur_slice])
                    ))

            for line_id, loan_id in cursor.fetchall():
                result[line_id] = loan_id

        return result
