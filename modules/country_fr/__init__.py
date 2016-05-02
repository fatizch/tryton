from trytond.pool import Pool
from .country import *


def register():
    Pool.register(
        Zip,
        module='country_fr', type_='model')
