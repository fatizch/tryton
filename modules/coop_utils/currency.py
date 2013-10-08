from decimal import ROUND_HALF_UP
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta

__all__ = ['Currency']


class Currency():
    'Currency'

    __name__ = 'currency.currency'

    def round(self, amount, rounding=ROUND_HALF_UP):
        return super(Currency, self).round(amount, rounding)
