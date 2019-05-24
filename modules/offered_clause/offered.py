# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields, model, coog_string

__all__ = [
    'Product',
    'ProductClauseRelation',
    ]


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    clauses = fields.Many2Many('offered.product-clause', 'product', 'clause',
        'Clauses', help='Clauses defined for this product',
        domain=[('kind', '=', 'specific')])

    def get_documentation_structure(self):
        doc = super(Product, self).get_documentation_structure()
        doc['rules'].append(
            coog_string.doc_for_field(self, 'clauses'))
        return doc


class ProductClauseRelation(model.CoogSQL):
    'Product Clause Relation'

    __name__ = 'offered.product-clause'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')
    clause = fields.Many2One('clause', 'Clause', ondelete='RESTRICT')
