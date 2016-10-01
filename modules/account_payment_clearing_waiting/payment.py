# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import fields

__all__ = [
    'Journal',
    'Payment',
    ]


class Journal:
    __metaclass__ = PoolMeta
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
    __metaclass__ = PoolMeta
    __name__ = 'account.payment'

    @classmethod
    def fail(cls, payments):
        Move = Pool().get('account.move')
        clearing_moves = [payment.clearing_move for payment in payments
            if payment.clearing_move and payment.kind == 'receivable' and
            payment.journal.outstandings_waiting_account]
        waiting_moves = Move.create_waiting_moves(clearing_moves)
        if waiting_moves:
            Move.save(waiting_moves)
            Move.post(waiting_moves)
        super(Payment, cls).fail(payments)
