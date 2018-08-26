# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'Insurer',
    ]


class Insurer:
    __metaclass__ = PoolMeta
    __name__ = 'insurer'

    product = fields.Function(fields.Many2One('offered.product', 'Product'),
        'get_product', searcher='search_product')

    def get_rec_name(self, name):
        name = super(Insurer, self).get_rec_name(name)
        if not self.product:
            return name
        else:
            return '%s - %s' % (name, self.product.rec_name)

    def get_product(self, name):
        return (self.options[0].products[0].id
            if self.options and self.options[0].products else None)

    def get_func_key(self, name):
        return '%s|%s' % (self.party.code,
            self.product.code if self.product else None)

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 2:
                party_code, product_code = clause[2].split('|')
                return [('party.code', clause[1], party_code),
                    ('product.code', clause[1], product_code)]
            else:
                return [('id', '=', None)]
        else:
            return ['OR',
                [('party.code',) + tuple(clause[1:])],
                [('product.code',) + tuple(clause[1:])],
                ]

    @classmethod
    def search_product(cls, name, clause):
        return [('options.products',) + tuple(clause[1:])]
