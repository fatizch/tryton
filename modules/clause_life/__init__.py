from trytond.pool import Pool
from .clause import *


def register():
    Pool.register(
        # From file clause
        Clause,
        module='clause_life', type_='model')
