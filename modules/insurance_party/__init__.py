from trytond.pool import Pool
from .party import *


def register():
    Pool.register(
        Party,
        Insurer,
        Customer,
        module='insurance_party', type_='model')
