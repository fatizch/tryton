from trytond.pool import Pool

from .offered import *


def register():
    Pool.register(
        ProductPremiumDate,
        module='premium_life', type_='model')
