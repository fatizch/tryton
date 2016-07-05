# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .offered import *
from .clause import *


def register():
    Pool.register(
        Product,
        Clause,
        ProductClauseRelation,
        module='offered_clause', type_='model')
