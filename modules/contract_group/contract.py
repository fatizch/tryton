# -*- coding:utf-8 -*-
from trytond.pyson import Eval
from trytond.pool import PoolMeta
from trytond.pyson import If, Bool

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    ]


class Contract:
    __name__ = 'contract'

    is_group = fields.Function(
        fields.Boolean('Group Contract'),
        'get_is_group', searcher='search_is_group')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls.subscriber.domain = ['AND', cls.subscriber.domain,
            [If(
                    Bool(Eval('is_group')),
                    ('is_company', '=', True),
                    (),
                    )]
            ]
        cls.subscriber.depends += ['is_group']

    def get_is_group(self, name):
        return self.product.is_group if self.product else False

    @classmethod
    def search_is_group(cls, name, clause):
        return [('product.is_group', ) + tuple(clause[1:])]
