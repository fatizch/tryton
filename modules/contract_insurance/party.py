from trytond.pool import PoolMeta, Pool

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta

_all_ = [
    'Party',
    ]


class Party:
    __name__ = 'party.party'

    extra_data = fields.Dict('extra_data', 'Extra Data')
    extra_data_string = extra_data.translated('extra_data')
    covered_elements = fields.One2Many('contract.covered_element', 'party',
        'Covered Elements')

    def get_subscribed_contracts(self):
        Contract = Pool().get('contract')
        return Contract.search(['subscriber', '=', self.id])

    def get_all_contracts(self):
        Contract = Pool().get('contract')
        return Contract.search([('status', 'not in', ('terminated', 'void')),
                ['OR',
                    ('subscriber', '=', self),
                    ('covered_elements.party', '=', self)]])

    @staticmethod
    def default_extra_data():
        return {}

    @classmethod
    def _export_skips(cls):
        result = super(Party, cls)._export_skips()
        result.add('covered_elements')
        return result
