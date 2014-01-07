from decimal import ROUND_HALF_UP, Decimal
from trytond.pool import PoolMeta, Pool

from trytond.modules.coop_utils import export, utils

__metaclass__ = PoolMeta

__all__ = [
    'Currency',
    'CurrencyRate',
    ]

DEF_CUR_DIG = 2


class Currency(export.ExportImportMixin):
    __name__ = 'currency.currency'

    def round(self, amount, rounding=ROUND_HALF_UP):
        return super(Currency, self).round(amount, rounding)

    @classmethod
    def _export_keys(cls):
        return set(['code'])

    def get_amount_from_string(self, amount):
        from locale import atof
        amount = amount.strip(self.symbol)
        amount = amount.replace(self.mon_decimal_point, '.')
        return Decimal(atof(amount))

    def amount_as_string(self, amount, symbol=True, lang=None):
        Lang = Pool().get('ir.lang')
        if not lang:
            lang = utils.get_user_language()
        return Lang.currency(lang, amount, self, symbol=symbol)


class CurrencyRate(export.ExportImportMixin):
    'Currency Rate'

    __name__ = 'currency.currency.rate'
