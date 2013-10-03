from trytond.pool import Pool
from .contract import *


def register():
    Pool.register(
        # from Contract
        Contract,
        module='billing', type_='model')
