from trytond.pool import Pool
from .offered import *
from .clause import *


def register():
    Pool.register(
        Product,
        Clause,
        ProductClauseRelation,
        module='offered_clause', type_='model')
