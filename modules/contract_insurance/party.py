from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool

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

    @classmethod
    def view_attributes(cls):
        return super(Party, cls).view_attributes() + [(
                '/form/group[@id="party_extra_data"]',
                'states',
                {'invisible': ~Bool(Eval('extra_data', None))}
                )]

    @classmethod
    def copy(cls, parties, default=None):
        default = default.copy() if default else {}
        default.setdefault('covered_elements', None)
        return super(Party, cls).copy(parties, default=default)

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
