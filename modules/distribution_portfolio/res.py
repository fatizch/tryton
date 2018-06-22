# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

__all__ = [
    'User',
    ]


class User:
    __metaclass__ = PoolMeta
    __name__ = 'res.user'

    network_portfolios = fields.Function(
        fields.Many2Many('distribution.network', None, None, 'User Portfolios',
            states={
                'readonly': True,
                'invisible': ~Eval('dist_network')
                },
            depends=['dist_network']),
        'on_change_with_network_portfolios')

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._context_fields.append('network_portfolios')

    @fields.depends('dist_network')
    def on_change_with_network_portfolios(self, name=None):
        if not self.dist_network:
            return Pool().get('distribution.network').get_all_portfolios()
        return [x.id for x in self.dist_network.visible_portfolios]
