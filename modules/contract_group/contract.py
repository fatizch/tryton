# -*- coding:utf-8 -*-
from trytond.pyson import Eval
from trytond.pool import PoolMeta
from trytond.pyson import If, Bool

from trytond.modules.cog_utils import fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    ]


class Contract:
    __name__ = 'contract'

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
        super(Contract, cls).__setup__()

    def get_is_group(self, name):
        return self.offered.is_group if self.offered else False

    @classmethod
    def search_is_group(cls, name, clause):
        return [('offered.is_group', ) + tuple(clause[1:])]
