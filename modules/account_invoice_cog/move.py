# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'Move',
    'MoveLine',
    ]


class Move:
    __name__ = 'account.move'

    is_invoice_canceled = fields.Function(
        fields.Boolean('Invoice Canceled'),
        'get_is_invoice_canceled')
    invoice = fields.Function(
        fields.Many2One('account.invoice', 'Invoice'),
        'get_invoice')

    def get_is_invoice_canceled(self, name):
        return (self.is_origin_canceled and self.origin_item
            and self.origin_item.__name__ == 'account.invoice')

    @classmethod
    def get_invoice(cls, moves, name):
        pool = Pool()
        invoice = pool.get('account.invoice').__table__()
        cursor = Transaction().connection.cursor()
        result = {x.id: None for x in moves}

        move_ids = [move.id for move in moves]
        cursor.execute(*invoice.select(invoice.move, invoice.cancel_move,
            invoice.id,
            where=(invoice.move.in_(move_ids) |
                invoice.cancel_move.in_(move_ids)),
            group_by=[invoice.move, invoice.cancel_move, invoice.id]))

        for move, cancel_move, invoice in cursor.fetchall():
            result[move] = invoice
            result[cancel_move] = invoice
        return result


class MoveLine:
    __name__ = 'account.move.line'

    is_invoice_canceled = fields.Function(
        fields.Boolean('Invoice Canceled'),
        'get_move_field')

    def get_color(self, name):
        if self.is_invoice_canceled:
            return 'grey'
        color = super(MoveLine, self).get_color(name)
        amount = getattr(self.move.origin_item, 'total_amount', None)
        return 'red' if color == 'black' and amount < 0 else color
