from trytond.pool import Pool
from .zipcode import *


def register():
    Pool.register(
        Country,
        ZipCode,
        module='coop_country', type_='model')
