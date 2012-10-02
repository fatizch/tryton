#-*- coding:utf-8 -*-
from trytond.model import fields as fields

from trytond.pool import PoolMeta

from trytond.modules.coop_utils import CoopSQL, string as string
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

    def get_summary(self, name=None, at_date=None):
        res = super(Party, self).get_summary(name, at_date)
        if self.insurer_role:
            res += string.get_field_as_summary(self, 'insurer_role', True,
                at_date)
        if self.broker_role:
            res += string.get_field_as_summary(self, 'broker_role', True,
                at_date)
        if self.customer_role:
            res += string.get_field_as_summary(self, 'broker_role', True,
                at_date)
        return res


class Insurer(CoopSQL, Actor):
    'Insurer'

    __name__ = 'party.insurer'

    def get_summary(self, name=None, at_date=None):
        return 'X'


class Broker(CoopSQL, Actor):
    'Broker'

    __name__ = 'party.broker'

    def get_summary(self, name=None, at_date=None):
        return 'X'


class Customer(CoopSQL, Actor):
    'Customer'

    __name__ = 'party.customer'

    def get_summary(self, name=None, at_date=None):
        return 'X'
