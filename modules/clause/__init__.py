from trytond.pool import Pool
from .clause import *


def register():
    Pool.register(
        # From file clause
        Clause,
        ClauseVersion,
        module='clause', type_='model')
