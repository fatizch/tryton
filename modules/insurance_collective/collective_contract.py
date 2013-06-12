#-*- coding:utf-8 -*-
from trytond.pyson import Eval
from trytond.pool import PoolMeta
from trytond.pyson import If, Bool

from trytond.modules.coop_utils import fields, utils

__all__ = [
    'GroupContract',
    ]


class GroupContract():
    'Group Contract'

    __name__ = 'contract.contract'
    __metaclass__ = PoolMeta

    is_group = fields.Function(
        fields.Boolean('Group Contract',
            states={'invisible': Eval('product_kind') != 'insurance'}),
        'get_is_group', searcher='search_is_group')

    @classmethod
    def __setup__(cls):
        utils.update_domain(cls, 'subscriber', [If(
                    Bool(Eval('is_group')),
                    ('is_company', '=', True),
                    (),
                    )])
        utils.update_depends(cls, 'subscriber', ['is_group'])
        super(GroupContract, cls).__setup__()

    def get_is_group(self, name):
        return self.offered.is_group if self.offered else False

    @classmethod
    def search_is_group(cls, name, clause):
        return [('offered.is_group', ) + tuple(clause[1:])]
