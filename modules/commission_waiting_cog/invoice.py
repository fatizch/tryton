from __future__ import unicode_literals
from collections import defaultdict

from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'InvoiceLine'
    ]


class InvoiceLine:
    __name__ = 'account.invoice.line'

    def get_move_line(self):
        lines = super(InvoiceLine, self).get_move_line()
        if not self.from_commissions:
            return lines
        new_lines = []
        amounts = defaultdict(lambda: 0)
        for line in lines:
            if 'party' not in line:
                continue
            amounts[(line['account'], line['party'])] += (
                line['debit'] - line['credit'])
        for line in lines:
            if 'party' not in line:
                new_lines.append(line)
                continue
            if amounts[(line['account'], line['party'])] != 0:
                new_lines.append(line)
        return new_lines
