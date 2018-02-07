# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

__all__ = [
    'Party',
    'PartyIdentifier',
    ]


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    orias = fields.Function(
        fields.Char('ORIAS', states={'invisible': ~Eval('is_broker')},
            depends=['is_broker']),
        'get_identifier', searcher='search_identifier')


class PartyIdentifier:
    __metaclass__ = PoolMeta
    __name__ = 'party.identifier'

    @classmethod
    def get_types(cls):
        return super(PartyIdentifier, cls).get_types() + [('orias', 'ORIAS')]
