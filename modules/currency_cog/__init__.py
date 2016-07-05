# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .currency import *
from .model import *
from .test_case import *


def register():
    Pool.register(
        # From file currency
        Currency,
        CurrencyRate,
        # From file test_case
        TestCaseModel,
        module='currency_cog', type_='model')
