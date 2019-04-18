# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from sql.aggregate import Sum
from sql.conditionals import Case
from sql.functions import Abs
from itertools import groupby

from trytond.pool import PoolMeta, Pool
from trytond.server_context import ServerContext


__all__ = [
    'MoveLine',
    'Move',
    ]


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    def group_moves_for_snapshots(cls, moves):
        if ServerContext().get('disable_auto_aggregate', False):
            return []
        move_groups = []
        for move_group in super(Move, cls).group_moves_for_snapshots(moves):
            if len(move_group) == 1:
                move_groups.append(move_group)
                continue
            move_group.sort(key=cls.group_for_payment_cancellation)
            for _, group in groupby(move_group,
                    cls.group_for_payment_cancellation):
                move_groups.append(list(group))
        return move_groups

    @classmethod
    def group_for_payment_cancellation(cls, move):
        '''
            Used to find moves which are payment cancellations, since they
            should be merged together when cancelled.
        '''
        if not move.origin:
            return ''
        if move.origin.__name__ != 'account.move':
            return ''
        if getattr(move.origin.origin, '__name__', '') != 'account.payment':
            return ''
        if move.journal.aggregate_posting_behavior == 'always':
            return ''
        elif move.journal.aggregate_posting_behavior == 'except_payment_cancel':
            return move.origin.origin.merged_id


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    @classmethod
    def _search_payment_amount_tables(cls):
        pool = Pool()

        tables = super(MoveLine, cls)._search_payment_amount_tables()
        tables.update({
                'clearing_line': pool.get('account.move.line').__table__(),
                })
        return tables

    @classmethod
    def _search_payment_amount_join(cls, tables):
        payment_join = super(MoveLine, cls)._search_payment_amount_join(tables)
        move_line = tables['move_line']
        payment = tables['payment']
        clearing_line = tables['clearing_line']
        return payment_join.join(clearing_line, type_='LEFT',
            condition=((payment.clearing_move == clearing_line.move)
                & (move_line.account == clearing_line.account)
                & (move_line.reconciliation == Null)
                & (clearing_line.reconciliation != Null)))

    @classmethod
    def _search_payment_amount_amount(cls, tables):
        amount = super(MoveLine, cls)._search_payment_amount_amount(tables)

        clearing_line = tables['clearing_line']
        main_reconciled_amount = clearing_line.credit - clearing_line.debit
        second_reconciled_amount = clearing_line.amount_second_currency
        reconciled_amount = Case(
            (clearing_line.second_currency == Null, main_reconciled_amount),
            else_=second_reconciled_amount)
        amount = amount + Sum(Case(
                (clearing_line.reconciliation != Null, Abs(reconciled_amount)),
                else_=0))

        return amount
