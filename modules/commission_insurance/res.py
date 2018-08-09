# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'User',
    ]


class User:
    __metaclass__ = PoolMeta
    __name__ = 'res.user'

    broker_party = fields.Function(
        fields.Many2One('party.party', 'Broker Party'),
        'get_broker_party')

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._context_fields.append('broker_party')

    def get_broker_party(self, name):
        return self.dist_network.broker_party if self.dist_network else None
