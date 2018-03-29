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

    dist_network = fields.Many2One('distribution.network',
        'Distribution Network')
    network_distributors = fields.Function(
        fields.Many2Many('distribution.network', None, None,
            'User Network Distributors'), 'get_network_distributors')

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._context_fields.append('dist_network')

    @classmethod
    def _export_light(cls):
        result = super(User, cls)._export_light()
        result.add('dist_network')
        return result

    def get_network_distributors(self, name):
        if self.dist_network:
            candidates = [x.id for x in self.dist_network.all_children
            if x.is_distributor]
        else:
            candidates = [x.id for x in Pool().get(
                'distribution.network').search([('is_distributor', '=', True)])]
        return candidates
