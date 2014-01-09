from trytond.pool import Pool
from .offered import *


def register():
    Pool.register(
        # From file offered :
        CashValueRule,
        Product,
        OptionDescription,
        module='offered_cash_value', type_='model')
