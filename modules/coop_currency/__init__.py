from trytond.pool import Pool
from .currency import *
from .test_case import *


def register():
    Pool.register(
        # From file currency
        Currency,
        CurrencyRate,
        # From file test_case
        TestCaseModel,
        module='coop_currency', type_='model')
