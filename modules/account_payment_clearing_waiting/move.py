# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

__all__ = [
    'Move',
    ]


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'account.move'

    @classmethod
    def create_waiting_moves(cls, moves):
        if not moves:
            return []
        Move = Pool().get('account.move')
        waiting_moves = []
        for move in moves:
            if (not move.origin.journal.outstandings_journal or
                    not move.origin.journal.outstandings_waiting_account):
                continue
            default = move._cancel_default()
            default['origin'] = str(move.origin)
            default['journal'] = \
                move.origin.journal.outstandings_journal
            waiting_move, = Move.copy([move],
                default=default)
            waiting_move.cancel_move = None
            for line in waiting_move.lines:
                if line.credit or line.debit < 0:
                    origin_journal = move.origin.journal
                    line.account = \
                        origin_journal.outstandings_waiting_account
            waiting_move.lines = waiting_move.lines
            waiting_moves.append(waiting_move)
        return waiting_moves
