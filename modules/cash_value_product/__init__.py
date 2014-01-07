from trytond.pool import Pool
from .product import *


def register():
    Pool.register(
        # From file product :
        CashValueRule,
        Product,
        OptionDescription,
        module='cash_value_product', type_='model')
