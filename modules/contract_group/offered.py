# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, coog_string

__all__ = [
    'Product',
    'OptionDescription',
    'ItemDesc',
    ]


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    is_group = fields.Boolean('Group Product', help='Define if the product is '
        'a group product')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls.coverages.domain = ['AND', cls.coverages.domain,
            [('is_group', '=', Eval('is_group'))]
            ]
        cls.coverages.depends.append('is_group')

    def get_documentation_structure(self):
        doc = super(Product, self).get_documentation_structure()
        doc['parameters'].append(
            coog_string.doc_for_field(self, 'is_group'))
        return doc


class OptionDescription(metaclass=PoolMeta):
    __name__ = 'offered.option.description'

    is_group = fields.Boolean('Group Coverage', help='Define if the coverage '
        'is available only for a group product')

    def get_documentation_structure(self):
        doc = super(OptionDescription, self).get_documentation_structure()
        doc['parameters'].append(
            coog_string.doc_for_field(self, 'is_group'))
        return doc


class ItemDesc(metaclass=PoolMeta):
    __name__ = 'offered.item.description'

    @classmethod
    def __setup__(cls):
        super(ItemDesc, cls).__setup__()
        cls.kind.selection.append(('subsidiary', 'Subsidiary'))
