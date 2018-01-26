# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields, model

__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'ProductClauseRelation',
    ]


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'offered.product'

    clauses = fields.Many2Many('offered.product-clause', 'product', 'clause',
        'Clauses', domain=[('kind', '=', 'specific')])


class ProductClauseRelation(model.CoogSQL):
    'Product Clause Relation'

    __name__ = 'offered.product-clause'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')
    clause = fields.Many2One('clause', 'Clause', ondelete='RESTRICT')
