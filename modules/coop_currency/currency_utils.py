from decimal import Decimal

from trytond.pool import Pool
from trytond.modules.coop_utils import utils


__all__ = [
    'get_amount_from_currency',
    'amount_as_string',
]


def get_amount_from_currency(amount, currency):
    from locale import atof
    amount = amount.strip(currency.symbol)
    amount = amount.replace(currency.mon_decimal_point, '.')
    return Decimal(atof(amount))


def amount_as_string(amount, currency, symbol=True, lang=None):
    Lang = Pool().get('ir.lang')
    if not lang:
        lang = utils.get_user_language()
    return Lang.currency(lang, amount, currency, symbol=symbol)
