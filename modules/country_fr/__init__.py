from trytond.pool import Pool
from .zipcode import *


def register():
    Pool.register(
        ZipCode,
        module='country_fr', type_='model')
