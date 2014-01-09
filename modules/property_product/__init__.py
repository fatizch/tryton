from trytond.pool import Pool
from .offered import *


def register():
    Pool.register(
        # From offered
        OptionDescription,
        module='property_product', type_='model')
