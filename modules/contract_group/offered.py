# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'OptionDescription',
    ]


class Product:
    __name__ = 'offered.product'

    is_group = fields.Boolean('Group Product')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls.coverages.domain = ['AND', cls.coverages.domain,
            [('is_group', '=', Eval('is_group'))]
            ]
        cls.coverages.depends.append('is_group')


class OptionDescription:
    __name__ = 'offered.option.description'

    is_group = fields.Boolean('Group Coverage')
