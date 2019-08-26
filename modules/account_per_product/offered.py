# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.exceptions import UserWarning
from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.model import Unique
from trytond.pyson import Eval

__all__ = [
    'Product',
    'ProductOptionDescriptionRelation',
    ]


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls.coverages.domain.extend([
                ('OR', ('products', '=', None), ('products', '=', Eval('id'))),
                ])
        cls.coverages.depends.append('id')

    @classmethod
    def validate(cls, products):
        super(Product, cls).validate(products)
        for product in products:
            cls.check_insurer(product)

    def check_insurer(self):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        for coverage in self.coverages:
            products = list(set(p for p in coverage.insurer.get_products()
                    if p and p != self))
            if len(products) > 0:
                key = 'mixing_products_%s' % coverage.id
                if Warning.check(key):
                    raise UserWarning(key, gettext(
                            'account_per_product.msg_mixing_products',
                            coverage_code=coverage.code,
                            coverage_name=coverage.name,
                            products=', '.join(p.rec_name for p in products)))


class ProductOptionDescriptionRelation(metaclass=PoolMeta):
    __name__ = 'offered.product-option.description'

    @classmethod
    def __setup__(cls):
        super(ProductOptionDescriptionRelation, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('unique_product_to_coverage', Unique(t, t.coverage),
                'The coverage can have a relation with only one product'),
            ]
