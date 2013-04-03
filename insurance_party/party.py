#-*- coding:utf-8 -*-
from trytond.pool import PoolMeta
from trytond.pyson import Not

from trytond.modules.coop_utils import model, fields, coop_string
from trytond.modules.coop_party import Actor
from trytond.modules.coop_party.party import STATES_COMPANY

__all__ = [
    'Party',
    'Insurer',
    'Broker',
    'Customer',
]


class Party:
    'Party'

    __name__ = 'party.party'
    __metaclass__ = PoolMeta

    insurer_role = fields.One2Many('party.insurer', 'party', 'Insurer', size=1,
        states={'invisible': Not(STATES_COMPANY)})
    broker_role = fields.One2Many('party.broker', 'party', 'Broker', size=1)
    customer_role = fields.One2Many('party.customer', 'party', 'Customer',
        size=1)

    @classmethod
    def get_summary(cls, parties, name=None, at_date=None, lang=None):
        res = super(Party, cls).get_summary(
            parties, name=name, at_date=at_date, lang=lang)
        for party in parties:
            if party.insurer_role:
                res[party.id] += coop_string.get_field_as_summary(party,
                    'insurer_role', True, at_date, lang=lang)
            if party.broker_role:
                res[party.id] += coop_string.get_field_as_summary(party,
                    'broker_role', True, at_date, lang=lang)
            if party.customer_role:
                res[party.id] += coop_string.get_field_as_summary(party,
                    'broker_role', True, at_date, lang=lang)
        return res


class Insurer(Actor, model.CoopSQL):
    'Insurer'

    __name__ = 'party.insurer'

    @classmethod
    def get_summary(cls, insurers, name=None, at_date=None, lang=None):
        return dict([(insurer.id, 'X') for insurer in insurers])


class Broker(Actor, model.CoopSQL):
    'Broker'

    __name__ = 'party.broker'

    @classmethod
    def get_summary(cls, brokers, name=None, at_date=None, lang=None):
        return dict([(broker.id, 'X') for broker in brokers])


class Customer(Actor, model.CoopSQL):
    'Customer'

    __name__ = 'party.customer'

    @classmethod
    def get_summary(cls, customers, name=None, at_date=None, lang=None):
        return dict([(customer.id, 'X') for customer in customers])
