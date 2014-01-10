#-*- coding:utf-8 -*-
import copy

from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import utils, fields

__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'OptionDescription',
    ]


class Product:
    __name__ = 'offered.product'

    is_group = fields.Boolean('Group Product',
        states={'invisible': Eval('kind') != 'insurance'})

    @classmethod
    def __setup__(cls):
        utils.update_domain(
            cls, 'coverages', [('is_group', '=', Eval('is_group'))])
        cls.coverages = copy.copy(cls.coverages)
        cls.coverages.depends.append('is_group')
        super(Product, cls).__setup__()


class OptionDescription:
    __name__ = 'offered.option.description'

    is_group = fields.Boolean('Group Coverage',
        states={'invisible': Eval('kind') != 'insurance'})

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        utils.update_domain(cls, 'coverages_in_package',
            [('is_group', '=', Eval('is_group'))])
        utils.update_depends(cls, 'coverages_in_package', ['is_group'])
