from trytond.pool import Pool

from .utils import get_coop_config


class ArgsDoNotMatchException(Exception):
    pass


def get_default_currency():
    cur_code = get_coop_config('localization', 'currency')
    Currency = Pool().get('currency.currency')
    currencies = Currency.search([('code', '=', cur_code)], limit=1)
    if len(currencies) > 0:
        return currencies[0].id


def get_default_country():
    cur_code = get_coop_config('localization', 'country')
    Country = Pool().get('country.country')
    countries = Country.search([('code', '=', cur_code)], limit=1)
    if len(countries) > 0:
        return countries[0].id


def update_args_with_subscriber(args):
    subscriber = None
    if 'contract' in args:
        subscriber = args['contract'].subscriber
        args['subscriber'] = subscriber
    elif 'subscriber' in args:
        subscriber = args['subscriber']
    if not subscriber:
        raise ArgsDoNotMatchException
    if subscriber.__name__ == 'party.party':
        if hasattr(subscriber, 'is_person') and subscriber.is_person:
            args['subscriber_person'] = subscriber
        elif hasattr(subscriber, 'is_society') and subscriber.is_society:
            args['subscriber_society'] = subscriber
        return
