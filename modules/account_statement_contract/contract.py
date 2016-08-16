# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Cast
from sql.operators import Concat

from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import fields
from trytond.tools import grouped_slice

__all__ = [
    'Contract',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    cancelled_statements = fields.Function(
        fields.Many2Many('account.statement', None, None,
            'Cancelled Statements'),
        'get_cancelled_statements')

    @classmethod
    def get_cancelled_statements(cls, contracts, name=None):
        pool = Pool()
        stmt_line = pool.get('account.statement.line').__table__()
        Move = pool.get('account.move')
        move_line = pool.get('account.move.line').__table__()
        move = Move.__table__()
        cursor = Transaction().connection.cursor()

        result = {x.id: [] for x in contracts}
        query_table = stmt_line.join(move_line,
            condition=move_line.move == stmt_line.move
            ).join(move, condition=move.origin == Concat(
                    'account.move,', Cast(stmt_line.move, 'VARCHAR')))
        for contract_slice in grouped_slice(contracts):
            contract_ids = [x.id for x in contract_slice]
            cursor.execute(*query_table.select(
                    move_line.contract, stmt_line.statement,
                    where=(move_line.contract.in_(contract_ids)),
                    group_by=[move_line.contract, stmt_line.statement]))
            for contract, statement in cursor.fetchall():
                result[contract].append(statement)
        return result
