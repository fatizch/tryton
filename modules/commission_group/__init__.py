from trytond.pool import Pool
from .billing import *


def register():
    Pool.register(
        PremiumRateFormLine,
        module='commission_group', type_='model')
