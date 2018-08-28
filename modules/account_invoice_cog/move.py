# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.modules.coog_core import fields

__all__ = [
    'Move',
    'MoveLine',
    ]


class Move:
    __metaclass__ = PoolMeta
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
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'

    is_invoice_canceled = fields.Function(
        fields.Boolean('Invoice Canceled'),
        'get_move_field')

    @classmethod
    def _key_func_for_reconciliation_order(cls, obj):
        if obj.origin and obj.origin.__name__ == 'account.invoice':
            return (obj.maturity_date or datetime.date.min,
                obj.origin.start or obj.date, obj.create_date)
        return super(MoveLine, cls)._key_func_for_reconciliation_order(obj)

    @classmethod
    def _update_per_invoice_origin(cls, per_invoice, line):
        if not line.origin:
            return None
        if (line.origin.__name__ == 'account.invoice' and
                line.origin.move == line.move):
            per_invoice[line.origin]['base'].append(line)
            return 'base'
        elif (line.origin.__name__ == 'account.move' and
                line.origin.origin.__name__ == 'account.invoice' and
                line.origin.origin.cancel_move == line.move):
            per_invoice[line.origin.origin]['canceled'].append(line)
            return 'canceled'
        elif (line.origin.__name__ == 'account.payment' and
                line.origin.line and line.origin.line.origin and
                line.origin.line.origin.__name__ == 'account.invoice' and
                line.origin.line.origin.move == line.origin.line.move):
            per_invoice[line.origin.line.origin]['paid'].append(line)
            return 'paid'
        return None

    @classmethod
    def reconcile_perfect_lines(cls, lines):
        """
        Find out which lines are matching perfectly to reconcile them
        together
        This use invoice states as sections to group lines for the perfect
        check
        """
        sections = ['base', 'canceled', 'paid']
        per_invoice = defaultdict(
            lambda: {section: [] for section in sections})
        unmatched = []
        for line in lines:
            if cls._update_per_invoice_origin(per_invoice, line):
                continue
            unmatched.append(line)

        matched = []
        for data in per_invoice.values():
            base_lines, cancel_lines, pay_lines = [data[x] for x in
                sections]
            if cancel_lines:
                if not base_lines:
                    unmatched.extend(cancel_lines + pay_lines)
                    continue
                base_and_cancel = base_lines + cancel_lines
                assert sum(x.amount for x in base_and_cancel) == 0
                matched.append((base_and_cancel, 0))
                unmatched.extend(pay_lines)
                continue
            if pay_lines:
                per_line = {x.origin.line: x for x in pay_lines}
                for line in base_lines:
                    if line not in per_line:
                        unmatched.append(line)
                        continue
                    if per_line[line].amount + line.amount != 0:
                        unmatched.extend([line, per_line.pop(line)])
                        continue
                    matched.append(([line, per_line.pop(line)], 0))
                unmatched.extend(per_line.values())
            if base_lines and not cancel_lines and not pay_lines:
                unmatched.extend(base_lines)
        return (matched, unmatched)

    def get_color(self, name):
        if self.is_invoice_canceled:
            return 'grey'
        color = super(MoveLine, self).get_color(name)
        amount = getattr(self.move.origin_item, 'total_amount', None)
        return 'red' if color == 'black' and amount < 0 else color
