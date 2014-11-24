from trytond.pool import Pool
from .commission import *


def register():
    Pool.register(
        Commission,
        module='commission_waiting_cog', type_='model')
