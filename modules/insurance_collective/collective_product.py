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

    __name__ = 'offered.product'
    __metaclass__ = PoolMeta

    is_group = fields.Boolean('Group Product',
        states={'invisible': Eval('kind') != 'insurance'})

    @classmethod
    def __setup__(cls):
        utils.update_domain(
            cls, 'coverages', [('is_group', '=', Eval('is_group'))])
        cls.coverages = copy.copy(cls.coverages)
        cls.coverages.depends.append('is_group')
        super(GroupProduct, cls).__setup__()


class GroupCoverage():
    'Group Coverage'

    __name__ = 'offered.coverage'
    __metaclass__ = PoolMeta

    is_group = fields.Boolean('Group Coverage')

    @classmethod
    def __setup__(cls):
        super(GroupCoverage, cls).__setup__()
        utils.update_domain(cls, 'coverages_in_package',
            [('is_group', '=', Eval('is_group'))])
        utils.update_depends(cls, 'coverages_in_package', ['is_group'])


class GroupBenefit():
    'Benefit'

    __name__ = 'ins_product.benefit'
    __metaclass__ = PoolMeta

    @classmethod
    def get_beneficiary_kind(cls):
        res = super(GroupBenefit, cls).get_beneficiary_kind()
        res.append(['affiliated', 'Affiliated'])
        return res
