from trytond.pool import PoolMeta
from trytond.transaction import Transaction

import string_utils

__metaclass__ = PoolMeta
__all__ = [
    'Currency',
    ]


class Currency:
    __name__ = 'currency.currency'

    @classmethod
    def __setup__(cls):
        super(Currency, cls).__setup__()
        cls._error_messages.update({
                'floating_separator_string': 'and',
                })

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
