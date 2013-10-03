from trytond.pool import Pool
from .billing import *


def register():
    Pool.register(
        #From billing
        RateNoteLine,
        module='commission_collective', type_='model')
