# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal, Null

from trytond import backend

from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool, If
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields

__all__ = [
    'DistributionNetwork',
    ]


class DistributionNetwork:
    __metaclass__ = PoolMeta
    __name__ = 'distribution.network'

    is_broker = fields.Boolean('Broker',
         states={'readonly': ~Eval('party')},
         domain=[If(Bool(Eval('is_broker', False)),
                    [('party', '!=', None)],
                    [])],
         depends=['party'])
    broker_party = fields.Function(
        fields.Many2One('party.party', 'Broker Party'),
        'get_broker_party', searcher='search_broker_party')
    parent_brokers = fields.Function(
        fields.Many2Many('distribution.network', None, None, 'Parent Brokers'),
        'getter_parent_brokers')

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.14 : add is_broker field, initialize from party field
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        do_migrate = False
        table_handler = TableHandler(cls)
        do_migrate = not table_handler.column_exist('is_broker')
        super(DistributionNetwork, cls).__register__(module_name)
        if not do_migrate:
            return
        table = cls.__table__()
        cursor.execute(*table.update(columns=[table.is_broker],
                values=[Literal(True)], where=(table.party != Null)))
        cursor.execute(*table.update(columns=[table.is_broker],
                values=[Literal(False)], where=(table.party == Null)))

    @staticmethod
    def default_is_broker():
        return False

    def getter_parent_brokers(self, name):
        return [x.id for x in list(self.parents) + [self] if x.is_broker]

    @fields.depends('is_broker', 'party')
    def on_change_with_is_broker(self):
        if self.party is None:
            return False
        return self.is_broker

    def get_broker_party(self, name):
        if self.party and self.is_broker:
            return self.party.id
        elif self.parent and self.parent.broker_party:
            return self.parent.broker_party.id

    @classmethod
    def search_broker_party(cls, name, clause):
        if clause[1] != '=':
            raise NotImplementedError
        networks = cls.search(['AND',
                [('party', '=', clause[2])],
                [('is_broker', '=', True)]])
        if len(networks) == 1:
            return ['OR', ('parents', '=', networks[0]),
                    ('party', '=', clause[2])]
        elif len(networks) > 1:
            return ['OR', ('parents', 'in', networks),
                    ('party', '=', clause[2])]
        else:
            return [('id', '=', None)]
