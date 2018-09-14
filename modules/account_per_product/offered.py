# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import Unique
from trytond.pyson import Eval

__all__ = [
    'Product',
    'ProductOptionDescriptionRelation',
    ]


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'offered.product'

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls.coverages.domain.extend([
                ('OR', ('products', '=', None), ('products', '=', Eval('id'))),
                ])
        cls.coverages.depends.append('id')


class ProductOptionDescriptionRelation:
    __metaclass__ = PoolMeta
    __name__ = 'offered.product-option.description'

    @classmethod
    def __setup__(cls):
        super(ProductOptionDescriptionRelation, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('unique_product_to_coverage', Unique(t, t.coverage),
                'The coverage can have a relation with only one product'),
            ]
