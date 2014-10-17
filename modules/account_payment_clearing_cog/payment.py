from trytond.pool import PoolMeta

__metaclass__ = PoolMeta


class Payment:
    __name__ = 'account.payment'

    def create_clearing_move(self, date=None):
        move = super(Payment, self).create_clearing_move(date)
        if move:
            move.description = self.journal.rec_name
        return move
