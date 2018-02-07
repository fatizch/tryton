# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import ROUND_HALF_UP
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import export, utils

import string_utils


__all__ = [
    'Currency',
    'CurrencyRate',
    ]

DEF_CUR_DIG = 2


class Currency(export.ExportImportMixin):
    __name__ = 'currency.currency'
    _func_key = 'code'

    @classmethod
    def __setup__(cls):
        super(Currency, cls).__setup__()
        cls._error_messages.update({
                'floating_separator_string': 'and',
                })

    def round(self, amount, rounding=ROUND_HALF_UP):
        return super(Currency, self).round(amount, rounding)

    def amount_as_string(self, amount, symbol=True, lang=None):
        Lang = Pool().get('ir.lang')
        if not lang:
            lang = utils.get_user_language()
        return Lang.currency(lang, amount, self, symbol=symbol, grouping=True)

    def format_string_amount(self, amount, lang_code=None):
        if lang_code is None:
            lang_code = Transaction().language
        assert lang_code, 'A valid language is required'
        string_amount = ''
        integer, decimal = string_utils.split_integer_decimal(
            amount)
        integer_string, decimal_string = string_utils.number_to_words(
            amount, lang=lang_code)
        if integer:
            currency_name = str(self.name).lower()
            string_amount += '%s %s' % (integer_string, currency_name)
            if integer > 1:
                string_amount += 's'
            if decimal:
                conjonction = self.raise_user_error(
                    'floating_separator_string',
                    raise_exception=False)
                string_amount += ' %s ' % conjonction
        if decimal:
            # TO DO: retrieve cent from the currency
            string_amount += '%s cent' % decimal_string
            if decimal > 1:
                string_amount += 's'
        return string_amount


class CurrencyRate(export.ExportImportMixin):
    'Currency Rate'

    __name__ = 'currency.currency.rate'
