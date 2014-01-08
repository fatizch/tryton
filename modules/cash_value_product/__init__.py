from trytond.pool import Pool
from .offered import *


def register():
    Pool.register(
        # From file offered :
        CashValueRule,
        Product,
        OptionDescription,
        module='cash_value_product', type_='model')
