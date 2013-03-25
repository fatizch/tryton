#-*- coding:utf-8 -*-
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coop_utils import utils, fields


__all__ = [
    'GroupProduct',
    'GroupCoverage',
]


class GroupProduct():
    'Group Product'

    __name__ = 'ins_product.product'
    __metaclass__ = PoolMeta

    is_group = fields.Boolean('Group Product')

    @classmethod
    def __setup__(cls):
        utils.update_domain(cls, 'options',
            [('is_group', '=', Eval('is_group'))])
        super(GroupProduct, cls).__setup__()


class GroupCoverage():
    'Group Coverage'

    __name__ = 'ins_product.coverage'
    __metaclass__ = PoolMeta

    is_group = fields.Boolean('Group Coverage')
