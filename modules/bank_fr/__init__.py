from trytond.pool import Pool
from .bank import *


def register():
    Pool.register(
        Bank,
        module='bank_fr', type_='model')
