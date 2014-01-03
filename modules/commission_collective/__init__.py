from trytond.pool import Pool
from .billing import *


def register():
    Pool.register(
        #From billing
        PremiumRateFormLine,
        module='commission_collective', type_='model')
