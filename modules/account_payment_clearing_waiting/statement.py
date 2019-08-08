# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.modules.coog_core import fields

__all__ = [
    'LineGroup',
    'StatementJournal',
    ]


class LineGroup(metaclass=PoolMeta):
    __name__ = 'account.statement.line.group'

    @classmethod
    def cancel(cls, line_groups, cancel_motive):
        Move = Pool().get('account.move')
        waiting_moves = Move.create_waiting_moves(
            [line_group.move for line_group in line_groups])
        if waiting_moves:
            Move.save(waiting_moves)
            Move.post(waiting_moves)
        super().cancel(line_groups, cancel_motive)


class StatementJournal(metaclass=PoolMeta):
    __name__ = 'account.statement.journal'

    outstandings_waiting_account = fields.Many2One('account.account',
       'Outstandings Waiting Account', domain=[
           ('company', '=', Eval('company')),
           ('kind', '=', 'other'),
           ],
       depends=['company'], ondelete='RESTRICT')
    outstandings_journal = fields.Many2One('account.journal',
       'Outstandings Journal', ondelete='RESTRICT')

    @classmethod
    def _export_light(cls):
        return super(StatementJournal, cls)._export_light() | {
            'outstandings_waiting_account',
            'outstandings_journal'}
