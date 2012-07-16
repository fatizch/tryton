#-*- coding:utf-8 -*-
from trytond.model import fields as fields

from trytond.pool import PoolMeta

from trytond.modules.coop_utils import CoopSQL
from trytond.modules.coop_party import Actor

__all__ = ['Party', 'Insurer', 'Broker', 'Customer', ]
__metaclass__ = PoolMeta


class Party:
    'Party'

    __name__ = 'party.party'

    insurer_role = fields.One2Many('party.insurer', 'party', 'Insurer', size=1)
    broker_role = fields.One2Many('party.broker', 'party', 'Broker', size=1)
    customer_role = fields.One2Many('party.customer', 'party', 'Customer',
        size=1)


class Insurer(CoopSQL, Actor):
    'Insurer'

    __name__ = 'party.insurer'


class Broker(CoopSQL, Actor):
    'Broker'

    __name__ = 'party.broker'


class Customer(CoopSQL, Actor):
    'Customer'

    __name__ = 'party.customer'
