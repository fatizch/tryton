from decimal import Decimal

from trytond.pool import Pool
from trytond.model import Model
from trytond.modules.coop_utils import utils


__all__ = [
    'CurrencyUtils',
]


class CurrencyUtils(Model):
    'Currency Utils'

    __name__ = 'utils.currency'

    @classmethod
    def get_amount_from_currency(cls, amount, currency):
        from locale import atof
        amount = amount.strip(currency.symbol)
        amount = amount.replace(currency.mon_decimal_point, '.')
        return Decimal(atof(amount))
