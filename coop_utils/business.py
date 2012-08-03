from trytond.pool import Pool

from .utils import get_coop_config


def get_default_currency():
    cur_code = get_coop_config('localization', 'currency')
    Currency = Pool().get('currency.currency')
    currencies = Currency.search([('code', '=', cur_code)], limit=1)
    if len(currencies) > 0:
        return currencies[0].id
