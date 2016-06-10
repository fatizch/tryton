# -*- coding:utf-8 -*-
from trytond.pyson import Eval
from trytond.pool import PoolMeta
from trytond.pyson import If, Bool

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'Option',
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


class Option:
    __name__ = 'contract.option'

    is_group = fields.Function(
        fields.Boolean('Group Option'),
        'on_change_with_is_group')

    @fields.depends('coverage')
    def on_change_with_is_group(self, name=None):
        if not self.coverage:
            return False
        return self.coverage.is_group
