from trytond.pool import PoolMeta, Pool

from trytond.modules.coop_utils import fields

_all_ = [
    'Party',
]


class Party:
    'Party'

    __name__ = 'party.party'
    __metaclass__ = PoolMeta

    complementary_data = fields.Dict('ins_product.complementary_data_def',
        'Complementary Data')
    covered_elements = fields.One2Many('ins_contract.covered_element',
        'party', 'Covered Elements')

    def get_subscribed_contracts(self):
        Contract = Pool().get('contract.contract')
        return Contract.search(['subscriber', '=', self.id])
