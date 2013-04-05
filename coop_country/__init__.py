from trytond.pool import Pool
from .zipcode import *


def register():
    Pool.register(
        Country,
        Subdivision,
        ZipCode,
        module='coop_country', type_='model')
