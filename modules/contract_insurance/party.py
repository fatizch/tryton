# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import fields


_all_ = [
    'Party',
    'PartyReplace',
    ]


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    covered_elements = fields.One2Many('contract.covered_element', 'party',
        'Covered Elements')

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

    @classmethod
    def _export_skips(cls):
        result = super(Party, cls)._export_skips()
        result.add('covered_elements')
        return result


class PartyReplace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('contract.covered_element', 'party'),
            ]
