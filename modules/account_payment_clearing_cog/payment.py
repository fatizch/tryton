# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.model import Workflow
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, model


__all__ = [
    'Journal',
    'Payment',
    ]


class Journal(metaclass=PoolMeta):
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


class Payment(metaclass=PoolMeta):
    __name__ = 'account.payment'

    @classmethod
    def __setup__(cls):
        super(Payment, cls).__setup__()
        cls.line.states.update({'required': Eval('state', '') != 'draft'})
        cls.line.depends.append('state')

    def create_clearing_move(self, date=None):
        if date is None:
            date = self.date
        move = super(Payment, self).create_clearing_move(date)
        if move:
            move.description = self.description or self.journal.rec_name
        return move

    @classmethod
    @model.CoogView.button
    @Workflow.transition('succeeded')
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
    @model.CoogView.button
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
        return gettext(
            'account_payment_clearing_cog.msg_reject_of',
            description=move_description)

    @classmethod
    def get_payment_moves(cls, payments):
        pool = Pool()
        Move = pool.get('account.move')
        clearing_moves = Move.search([
            ('origin', 'in', [str(x) for x in payments])])
        # Linked moves could be cancel moves or clearing waiting moves
        linked_moves = Move.search([
            ('origin', 'in', [str(x) for x in clearing_moves])])
        return clearing_moves + linked_moves
