# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.tools import grouped_slice
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields
__metaclass__ = PoolMeta
__all__ = [
    'Invoice',
    ]


class Invoice:
    __name__ = 'account.invoice'

    payments = fields.Function(
        fields.One2Many('account.payment', None, 'Payments',
            states={'invisible':
                (~Eval('move', False) | ~Eval('payments')),
                },
                depends=['move']),
        'get_payments')
    pending_payment = fields.Function(
        fields.Boolean('Pending Payment'),
        'get_pending_payment')
    credit_reconciliation_lines = fields.Function(
        fields.One2Many('account.move.line', None, 'Payment Lines',
            states={'invisible':
                ~Eval('move', False) | ~Eval('credit_reconciliation_lines')},
            depends=['move']),
        'get_credit_reconciliation_lines')

    @classmethod
    def get_payments(cls, invoices, name):
        pool = Pool()
        payment = pool.get('account.payment').__table__()
        line = pool.get('account.move.line').__table__()
        move = pool.get('account.move').__table__()
        invoice = cls.__table__()
        cursor = Transaction().connection.cursor()

        result = {x.id: [] for x in invoices}
        for invoices_slice in grouped_slice(invoices):
            query = payment.join(line,
                condition=(payment.line == line.id)
                ).join(move, condition=(line.move == move.id)
                ).join(invoice, condition=(invoice.move == move.id)
                ).select(invoice.id, payment.id,
                where=(invoice.id.in_([x.id for x in invoices_slice])),
                )
            cursor.execute(*query)
            for k, v in cursor.fetchall():
                result[k].append(v)
        return result

    def get_pending_payment(self, name):
        return self.state == 'posted' and bool([x for x in self.payments
                if x.state in ['approved', 'processing']])

    def get_credit_reconciliation_lines(self, name):
        if not self.move:
            return []
        Line = Pool().get('account.move.line')
        return [x.id for x in Line.search([
                    ('reconciliation.lines.move', '=', self.move),
                    ('credit', '>', 0)])]

    def get_color(self, name):
        if self.pending_payment:
            return 'green'
        return super(Invoice, self).get_color(name)
