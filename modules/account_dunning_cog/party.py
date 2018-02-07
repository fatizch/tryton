# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields, export

__all__ = [
    'Party',
    'PartyDunningProcedure',
    ]


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    dunning_allowed = fields.Function(fields.Boolean(
            'Dunning Allowed'),
        'get_dunning_allowed', searcher='search_dunning_allowed')

    @classmethod
    def _export_skips(cls):
        return super(Party, cls)._export_skips() | {'dunning_procedure'}

    def _dunning_allowed(self):
        return True

    @classmethod
    def get_dunning_allowed(cls, parties, name):
        return {x.id: x._dunning_allowed() for x in parties}

    @classmethod
    def non_customer_clause(cls, clause):
        return []

    @classmethod
    def search_dunning_allowed(cls, name, clause):
        return []


class PartyDunningProcedure(export.ExportImportMixin):
    __metaclass__ = PoolMeta
    __name__ = 'party.party.dunning_procedure'
