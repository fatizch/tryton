# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import fields

__all__ = [
    'User',
    ]


class User:
    __metaclass__ = PoolMeta
    __name__ = 'res.user'

    network_distributors = fields.Function(
        fields.Many2Many('distribution.network', None, None,
            'User Network Distributors'), 'get_network_distributors')

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._context_fields.append('network_distributors')

    def get_network_distributors(self, name):
        if self.dist_network:
            res = [x.id for x in self.dist_network.all_children
                if x.is_distributor]
        else:
            res = Pool().get('distribution.network').get_all_distributors()
        return res
