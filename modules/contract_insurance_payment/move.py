# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta

__all__ = [
    'MoveLine',
    ]


class MoveLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'

    @classmethod
    def payment_outstanding_group_clause(cls, lines, line_table):
        clause = super(MoveLine, cls).payment_outstanding_group_clause(lines,
            line_table)
        if not lines[0].contract:
            return clause
        return (line_table.contract == lines[0].contract.id) & clause

    @classmethod
    def _process_payment_key(cls, line):
        return super(MoveLine, cls)._process_payment_key(line) + \
            (line.contract, )
