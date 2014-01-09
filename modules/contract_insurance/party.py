from trytond.pool import PoolMeta, Pool

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta

_all_ = [
    'Party',
    ]


class Party:
    __name__ = 'party.party'

    complementary_data = fields.Dict('extra_data', 'Extra Data')
    covered_elements = fields.One2Many('contract.covered_element',
        'party', 'Covered Elements')

    def get_subscribed_contracts(self):
        Contract = Pool().get('contract')
        return Contract.search(['subscriber', '=', self.id])
