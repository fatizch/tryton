#-*- coding:utf-8 -*-
import copy

from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coop_utils import utils, fields


__all__ = [
    'GroupProduct',
    'GroupCoverage',
    'GroupBenefit',
]


class GroupProduct():
    'Group Product'

    __name__ = 'ins_product.product'
    __metaclass__ = PoolMeta

    is_group = fields.Boolean('Group Product')

    @classmethod
    def __setup__(cls):
        utils.update_domain(
            cls, 'options', [('is_group', '=', Eval('is_group'))])
        cls.options = copy.copy(cls.options)
        cls.options.depends.append('is_group')
        super(GroupProduct, cls).__setup__()


class GroupCoverage():
    'Group Coverage'

    __name__ = 'ins_product.coverage'
    __metaclass__ = PoolMeta

    is_group = fields.Boolean('Group Coverage')


class GroupBenefit():
    'Benefit'

    __name__ = 'ins_product.benefit'
    __metaclass__ = PoolMeta

    @classmethod
    def get_beneficiary_kind(cls):
        res = super(GroupBenefit, cls).get_beneficiary_kind()
        res.append(['affiliated', 'Affiliated'])
        return res
