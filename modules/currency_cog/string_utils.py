# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from num2words import num2words


def split_integer_decimal(number):
    integer = int(number)
    decimal = (number - integer) * 10**(-number.as_tuple()[2])
    return (integer, decimal)


def number_to_words(number, lang, ordinal=False):
    """
    Returns a Tuple with two values:
    ('Integer in words', 'decimals in words')
    """

    integer_string, decimal_string = split_integer_decimal(number)
    return (num2words(integer_string, ordinal, lang),
        num2words(decimal_string, ordinal, lang))
