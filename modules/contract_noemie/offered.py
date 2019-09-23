# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.modules.coog_core import fields

__all__ = [
    'ItemDescription',
    'Product',
    ]


class ItemDescription(metaclass=PoolMeta):
    __name__ = 'offered.item.description'

    is_noemie = fields.Boolean('Is Noemie Person',
        states={'invisible': Eval('kind') != 'person'},
        depends=['kind'],
        help='If True, covered elements using this item descriptor will have '
        'noemie related informations')

    @fields.depends('kind')
    def on_change_with_is_noemie(self):
        if self.kind != 'person':
            return False


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    is_noemie = fields.Boolean('Is Noemie Product',
        states={'invisible': Eval('subscriber_kind') != 'person'},
        depends=['subscriber_kind'],
        help='If true, all covered elements for contracts using this product '
        'will have noemie related information')

    @fields.depends('subscriber_kind')
    def on_change_with_is_noemie(self):
        if self.subscriber_kind != 'person':
            return False
