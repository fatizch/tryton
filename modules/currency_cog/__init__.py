# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import currency
import test_case

from model import ModelCurrency

__all__ = [
    'ModelCurrency',
    ]


def register():
    Pool.register(
        currency.Currency,
        currency.CurrencyRate,
        test_case.TestCaseModel,
        module='currency_cog', type_='model')
