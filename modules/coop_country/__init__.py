from trytond.pool import Pool
from .zipcode import *


def register():
    Pool.register(
        ZipCode,
        module='coop_country', type_='model')
