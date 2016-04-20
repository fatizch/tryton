from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields
from trytond.model import ModelView, ModelSQL

__all__ = [
    'PartyJournalRelation'
    ]


class PartyJournalRelation(ModelSQL, ModelView):
    'Party Journal Relation'
    __name__ = 'account.payment.party_journal_relation'

    party = fields.Many2One('party.party', 'Party', select=True)
    journal = fields.Many2One('account.payment.journal', 'Journal', select=True)

