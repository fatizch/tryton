# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta, Pool

from trytond.model import ModelView, Workflow


__all__ = [
    'Invoice',
    ]


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    @classmethod
    @Workflow.transition('paid')
    def paid(cls, invoices):
        super(Invoice, cls).paid(invoices)
        Pool().get('account.move').create_waiting_account_move(
            [i.move for i in invoices])

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, invoices):
        Pool().get('account.move').create_waiting_account_move(
            [i.move for i in invoices if i.state == 'paid'], cancel=True)
        super(Invoice, cls).post(invoices)
