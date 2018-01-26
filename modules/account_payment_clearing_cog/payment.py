# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView, Workflow
from trytond.pyson import Eval

from trytond.modules.coog_core import fields


__metaclass__ = PoolMeta
__all__ = [
    'Journal',
    'Payment',
    ]


class Journal:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.journal'
    post_clearing_move = fields.Boolean('Post Clearing Move')
    always_create_clearing_move = fields.Boolean(
        'Always Create Clearing Move', help='For payments that are failed '
        'before being succeeded (e.g: technical failure) a clearing move will '
        'be created when the payment is failed. The end result is similar to '
        'what would have happened if the payment had been succeeded and then '
        'failed')

    @staticmethod
    def default_post_clearing_move():
        return True

    @classmethod
    def _export_light(cls):
        return super(Journal, cls)._export_light() | {'clearing_account',
            'clearing_journal'}


class Payment:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment'

    @classmethod
    def __setup__(cls):
        super(Payment, cls).__setup__()
        cls.line.states.update({'required': Eval('state', '') != 'draft'})
        cls.line.depends.append('state')
        cls._error_messages.update({
                'reject_of': 'Reject of %s',
                })

    def create_clearing_move(self, date=None):
        if date is None:
            date = self.date
        move = super(Payment, self).create_clearing_move(date)
        if move:
            move.description = self.description or self.journal.rec_name
        return move

    @classmethod
    def succeed(cls, payments):
        pool = Pool()
        Move = pool.get('account.move')
        super(Payment, cls).succeed(payments)
        clearing_moves = [payment.clearing_move for payment in payments
            if (payment.clearing_move and payment.journal.post_clearing_move)]
        if clearing_moves:
            Move.post(clearing_moves)

    @classmethod
    def handle_moves_before_fail(cls, payments):
        pool = Pool()
        Move = pool.get('account.move')

        moves, to_post = [], []
        for payment in [x for x in payments if not x.clearing_move and
                x.journal.always_create_clearing_move]:
            move = payment.create_clearing_move()
            if move:
                moves.append(move)
                if payment.journal.post_clearing_move:
                    to_post.append(move)
        if moves:
            Move.save(moves)
            cls.write(*sum((([m.origin], {'clearing_move': m.id})
                        for m in moves), ()))
        if to_post:
            Move.post(to_post)

    @classmethod
    @ModelView.button
    @Workflow.transition('failed')
    def fail(cls, payments):
        pool = Pool()
        Move = pool.get('account.move')
        cls.handle_moves_before_fail(payments)
        clearing_moves = ['account.move,%s' % payment.clearing_move.id
            for payment in payments
            if payment.clearing_move and payment.journal.post_clearing_move]
        super(Payment, cls).fail(payments)
        cancel_moves = Move.search([
                ('origin', 'in', clearing_moves),
                ('state', '=', 'draft')])
        if cancel_moves:
            to_write = []
            for cancel_move in cancel_moves:
                to_write += [[cancel_move],
                    {'description': cls.get_move_reject_description(
                            cancel_move.description)}]
            Move.write(*to_write)
            Move.post(cancel_moves)

    @classmethod
    def get_move_reject_description(cls, move_description):
        return cls.raise_user_error('reject_of', (move_description,),
            raise_exception=False)
