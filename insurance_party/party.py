#-*- coding:utf-8 -*-
from trytond.model import fields

from trytond.pool import PoolMeta

from trytond.modules.coop_utils import CoopSQL, string
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

    @classmethod
    def get_summary(cls, parties, name=None, at_date=None, lang=None):
        res = super(Party, cls).get_summary(parties, name, at_date, lang=lang)
        for party in parties:
            if party.insurer_role:
                res[party.id] += string.get_field_as_summary(party,
                    'insurer_role', True, at_date, lang=lang)
            if party.broker_role:
                res[party.id] += string.get_field_as_summary(party,
                    'broker_role', True, at_date, lang=lang)
            if party.customer_role:
                res[party.id] += string.get_field_as_summary(party,
                    'broker_role', True, at_date, lang=lang)
        return res


class Insurer(CoopSQL, Actor):
    'Insurer'

    __name__ = 'party.insurer'

    @classmethod
    def get_summary(cls, insurers, name=None, at_date=None, lang=None):
        return dict([(insurer.id, 'X') for insurer in insurers])


class Broker(CoopSQL, Actor):
    'Broker'

    __name__ = 'party.broker'

    @classmethod
    def get_summary(cls, brokers, name=None, at_date=None, lang=None):
        return dict([(broker.id, 'X') for broker in brokers])


class Customer(CoopSQL, Actor):
    'Customer'

    __name__ = 'party.customer'

    @classmethod
    def get_summary(cls, customers, name=None, at_date=None, lang=None):
        return dict([(customer.id, 'X') for customer in customers])
