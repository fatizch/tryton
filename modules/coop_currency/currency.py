from decimal import ROUND_HALF_UP
from trytond.pool import PoolMeta

from trytond.modules.coop_utils import export

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


class CurrencyRate(export.ExportImportMixin):
    'Currency Rate'

    __name__ = 'currency.currency.rate'
