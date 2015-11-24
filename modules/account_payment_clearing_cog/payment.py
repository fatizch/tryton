from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView, Workflow

from trytond.modules.cog_utils import fields


__metaclass__ = PoolMeta
__all__ = [
    'Journal',
    'Payment',
    ]


class Journal:
    __name__ = 'account.payment.journal'
    post_clearing_move = fields.Boolean('Post Clearing Move')

    @classmethod
    def _export_light(cls):
        return super(Journal, cls)._export_light() | {'clearing_account',
            'clearing_journal'}


class Payment:
    __name__ = 'account.payment'

    def create_clearing_move(self, date=None):
        if date is None:
            date = self.date
        move = super(Payment, self).create_clearing_move(date)
        if move:
            move.description = self.journal.rec_name
        return move

    @classmethod
    @ModelView.button
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
    @ModelView.button
    @Workflow.transition('failed')
    def fail(cls, payments):
        pool = Pool()
        Move = pool.get('account.move')
        clearing_moves = ['account.move,%s' % payment.clearing_move.id
            for payment in payments
            if payment.clearing_move and payment.journal.post_clearing_move]
        super(Payment, cls).fail(payments)
        cancel_moves = Move.search([
                ('origin', 'in', clearing_moves),
                ('state', '=', 'draft')])
        if cancel_moves:
            Move.post(cancel_moves)
