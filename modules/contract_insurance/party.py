# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool

from trytond.modules.coog_core import fields, model, coog_string
from trytond.modules.offered.extra_data import with_extra_data


_all_ = [
    'Party',
    'PartyReplace',
    ]


class Party(with_extra_data(['covered_element']), metaclass=PoolMeta):
    __name__ = 'party.party'

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

    @classmethod
    def validate(cls, parties):
        super(Party, cls).validate(parties)
        cls.check_extra_data(parties)

    @classmethod
    def default_extra_data(cls):
        return {}

    @classmethod
    def check_extra_data(cls, parties):
        ExtraData = Pool().get('extra_data')
        with model.error_manager():
            for party in parties:
                ExtraData.check_extra_data(party, 'extra_data')

    def get_subscribed_contracts(self):
        Contract = Pool().get('contract')
        return Contract.search(['subscriber', '=', self.id])

    def get_all_contracts(self):
        Contract = Pool().get('contract')
        return Contract.search([('status', 'not in', ('terminated', 'void')),
                ['OR',
                    ('subscriber', '=', self),
                    ('covered_elements.party', '=', self)]])

    @classmethod
    def _export_skips(cls):
        result = super(Party, cls)._export_skips()
        result.add('covered_elements')
        return result

    def get_gdpr_data(self):
        res = super(Party, self).get_gdpr_data()
        ExtraData = Pool().get('extra_data')
        value_ = coog_string.translate_value
        extras = ExtraData.search([
                ('name', 'in', list(self.extra_data.keys())),
                ('gdpr', '=', True)])
        res.update({value_(extra, 'rec_name'): self.extra_data[extra.name]
                for extra in extras})
        return res


class PartyReplace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('contract.covered_element', 'party'),
            ]
