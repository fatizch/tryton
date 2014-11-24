from trytond.model import ModelView
from trytond.pool import Pool, PoolMeta

__all__ = [
    'Commission'
    ]
__metaclass__ = PoolMeta


class Commission:
    __name__ = 'commission'

    @classmethod
    @ModelView.button
    def create_waiting_move(cls, commissions):
        pool = Pool()
        Move = pool.get('account.move')
        super(Commission, cls).create_waiting_move(commissions)
        moves = [commission.waiting_move for commission in commissions
            if commission.waiting_move]
        Move.post(moves)
