from trytond.pool import Pool
from .party import *


def register():
    Pool.register(
        #From party
        broker,
        module='commission_orias', type_='model')
