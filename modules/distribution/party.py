# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    'PartyReplace',
    ]


class Party:
    __name__ = 'party.party'

    network = fields.One2Many('distribution.network', 'party', 'Network')

    @classmethod
    def view_attributes(cls):
        return super(Party, cls).view_attributes() + [(
                '/form/notebook/page[@name="network"]',
                'states',
                {'invisible': ~Eval('network')}
                )]


class PartyReplace:
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('distribution.network', 'party'),
            ]
