from trytond.pool import Pool
from .gbp_creation import *


def register():
    Pool.register(
        module='life_product_collective', type_='model')

    Pool.register(
        # GBPWizard,
        module='life_product_collective', type_='wizard')
