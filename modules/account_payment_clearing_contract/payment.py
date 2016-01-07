from trytond.pool import PoolMeta


__metaclass__ = PoolMeta
__all__ = [
    'Payment',
    ]


class Payment:
    __name__ = 'account.payment'

    def create_clearing_move(self, date=None):
        move = super(Payment, self).create_clearing_move(date)
        if move:
            for line in move.lines:
                if getattr(line, 'party', None):
                    line.contract = self.line.contract
        return move
