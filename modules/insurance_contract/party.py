from trytond.pool import PoolMeta, Pool

from trytond.modules.coop_utils import model, fields, coop_string
from trytond.modules.coop_party import Actor

__metaclass__ = PoolMeta

_all_ = [
    'Party',
    'Customer',
    ]


class Party:
    'Party'

    __name__ = 'party.party'

    complementary_data = fields.Dict('extra_data',
        'Complementary Data')
    covered_elements = fields.One2Many('contract.covered_element',
        'party', 'Covered Elements')
    customer_role = fields.One2Many('customer', 'party', 'Customer',
        size=1)

    @classmethod
    def _export_force_recreate(cls):
        result = super(Party, cls)._export_force_recreate()
        result.remove('customer_role')
        return result

    @classmethod
    def get_summary(cls, parties, name=None, at_date=None, lang=None):
        res = super(Party, cls).get_summary(
            parties, name=name, at_date=at_date, lang=lang)
        for party in parties:
            if party.customer_role:
                res[party.id] += coop_string.get_field_as_summary(party,
                    'customer_role', True, at_date, lang=lang)
        return res

    def get_subscribed_contracts(self):
        Contract = Pool().get('contract')
        return Contract.search(['subscriber', '=', self.id])


class Customer(Actor, model.CoopSQL):
    'Customer'

    __name__ = 'customer'

    @classmethod
    def get_summary(cls, customers, name=None, at_date=None, lang=None):
        return dict([(customer.id, 'X') for customer in customers])
