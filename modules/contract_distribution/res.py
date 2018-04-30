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
    def get_network_distributors(cls, records, name):
        res = {}
        defaults = None
        for record in records:
            if record.dist_network:
                res[record.id] = [x.id for x in record.dist_network.all_children
                    if x.is_distributor]
            else:
                if defaults is None:
                    defaults = [x.id for x in Pool().get(
                            'distribution.network').search(
                            [('is_distributor', '=', True)])]
                res[record.id] = defaults
        return res
