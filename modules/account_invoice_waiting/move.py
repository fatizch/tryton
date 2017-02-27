# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.modules.coog_core import utils

__all__ = [
    'Move',
    ]


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'account.move'

    def _create_waiting_account_move(self, cancel):
        pool = Pool()
        Line = pool.get('account.move.line')
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        company = Transaction().context.get('company')
        lines = [l for l in self.lines if l.account.waiting_for_account]
        if not lines:
            return None

        move = Move()
        move.journal = self.journal
        move.company = company
        move.period = Period.find(company, date=utils.today())
        move.date = utils.today()
        move.origin = lines[0].move.origin
        move.description = self.description
        lines_waiting_account = [Line(**{
                    'move': move,
                    'debit': x.credit if not cancel else x.debit,
                    'credit': x.debit if not cancel else x.credit,
                    'account': x.account.id,
                    'description': x.description,
                    'date': utils.today(),
                    'party': x.origin.party if x.account.party_required else
                        None,
                    })
            for x in lines]
        waiting_lines_to_destination_account = [Line(**{
                    'move': move,
                    'debit': x.debit if not cancel else x.credit,
                    'credit': x.credit if not cancel else x.debit,
                    'account': x.account.waiting_for_account.id,
                    'description': x.description,
                    'date': utils.today(),
                    'party': x.origin.party if
                        x.account.waiting_for_account.party_required else None,
                    })
            for x in lines]
        move.lines = lines_waiting_account + \
            waiting_lines_to_destination_account
        return move

    @classmethod
    def create_waiting_account_move(cls, moves, cancel=False):
        waiting_moves = []
        for move in moves:
            waiting_move = move._create_waiting_account_move(cancel)
            if waiting_move:
                waiting_moves.append(waiting_move)
        if waiting_moves:
            cls.save(waiting_moves)
            cls.post(waiting_moves)
