from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields, model

__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'ProductClauseRelation',
    ]


class Product:
    __name__ = 'offered.product'

    clauses = fields.Many2Many('offered.product-clause', 'product', 'clause',
        'Clauses', domain=[('kind', '=', 'specific')])


class ProductClauseRelation(model.CoopSQL):
    'Product Clause Relation'

    __name__ = 'offered.product-clause'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')
    clause = fields.Many2One('clause', 'Clause', ondelete='RESTRICT')
