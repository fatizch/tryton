from decimal import ROUND_HALF_UP
from trytond.pool import PoolMeta, Pool

from trytond.modules.coop_utils import export, utils

__metaclass__ = PoolMeta

__all__ = [
    'Currency',
    'CurrencyRate',
]


class Currency(export.ExportImportMixin):
    'Currency'

    __name__ = 'currency.currency'

    def round(self, amount, rounding=ROUND_HALF_UP):
        return super(Currency, self).round(amount, rounding)

    @classmethod
    def _export_keys(cls):
        return set(['code'])

    def amount_as_string(self, amount, symbol=True, lang=None):
        Lang = Pool().get('ir.lang')
        if not lang:
            lang = utils.get_user_language()
        return Lang.currency(lang, amount, self, symbol=symbol)


class CurrencyRate(export.ExportImportMixin):
    'Currency Rate'

    __name__ = 'currency.currency.rate'
