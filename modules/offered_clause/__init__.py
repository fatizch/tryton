# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import offered
from . import clause


def register():
    Pool.register(
        offered.Product,
        clause.Clause,
        offered.ProductClauseRelation,
        module='offered_clause', type_='model')
