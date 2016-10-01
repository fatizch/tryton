# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.coog_core import fields
from trytond.model import ModelView, ModelSQL

__all__ = [
    'PartyJournalRelation'
    ]


class PartyJournalRelation(ModelSQL, ModelView):
    'Party Journal Relation'
    __name__ = 'account.payment.party_journal_relation'

    party = fields.Many2One('party.party', 'Party', select=True)
    journal = fields.Many2One('account.payment.journal', 'Journal',
        select=True)
