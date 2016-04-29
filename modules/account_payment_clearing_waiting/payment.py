from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Journal',
    'Payment',
    ]


class Journal:
    __name__ = 'account.payment.journal'

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
        return super(Journal, cls)._export_light() | {
            'outstandings_waiting_account',
            'outstandings_journal'}


class Payment:
    __name__ = 'account.payment'

    @classmethod
    def fail(cls, payments):
        Move = Pool().get('account.move')
        clearing_moves = [payment.clearing_move for payment in payments
            if payment.clearing_move and payment.kind == 'receivable' and
            payment.journal.outstandings_waiting_account]
        if clearing_moves:
            waiting_moves = []
            for clearing_move in clearing_moves:
                default = clearing_move._cancel_default()
                default['origin'] = str(clearing_move.origin)
                default['journal'] = \
                    clearing_move.origin.journal.outstandings_journal
                waiting_move, = Move.copy([clearing_move],
                    default=default)
                for line in waiting_move.lines:
                    if line.credit or line.debit < 0:
                        origin_journal = clearing_move.origin.journal
                        line.account = \
                            origin_journal.outstandings_waiting_account
                waiting_move.lines = waiting_move.lines
                waiting_moves.append(waiting_move)
            Move.save(waiting_moves)
            Move.post(waiting_moves)
        super(Payment, cls).fail(payments)
