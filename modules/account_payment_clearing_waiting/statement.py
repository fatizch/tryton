# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.modules.cog_utils import fields

__all__ = [
    'CancelLineGroup',
    'StatementJournal',
    ]


class CancelLineGroup:
    __metaclass__ = PoolMeta
    __name__ = 'account.statement.line.group.cancel'

    def do_cancel(self, action):
        Move = Pool().get('account.move')
        waiting_moves = Move.create_waiting_moves(self.start.moves)
        if waiting_moves:
             Move.save(waiting_moves)
             Move.post(waiting_moves)
        return super(CancelLineGroup, self).do_cancel(action)


class StatementJournal:
    __metaclass__ = PoolMeta
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
