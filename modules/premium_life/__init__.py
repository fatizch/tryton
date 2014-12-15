from trytond.pool import Pool

from .offered import *

def register():
    Pool.register(
        ProductPremiumDates,
        module='premium_life', type_='model')
