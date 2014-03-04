from trytond.pool import Pool
from .clause import *
from .clause_rule import *


def register():
    Pool.register(
        # From file clause
        Clause,
        # From file clause_rule
        ClauseRule,
        module='clause_life', type_='model')
