#-*- coding:utf-8 -*-
import datetime

from trytond.model import fields as fields
from trytond.pool import Pool
from trytond.modules.coop_utils import CoopView, CoopSQL, TableOfTable

__all__ = ['PartyRelationKind', 'PartyRelation']


class PartyRelationKind(TableOfTable):
    'Party Relation'

    __name__ = 'party.party_relation_kind'
    _table = 'coop_table_of_table'

    @classmethod
    def __setup__(cls):
        super(PartyRelationKind, cls).__setup__()
        cls._sql_constraints += [
            ('key_uniq', 'UNIQUE(key)', 'The key must be unique!'),
        ]

    def get_reverse_relation(self):
        if self.parent:
            return self.parent
        if self.childs and len(self.childs) > 0:
            return self.childs[0]


class PartyRelation(CoopSQL, CoopView):
    'Party Relation'

    __name__ = 'party.party-relation'

    from_party = fields.Many2One('party.party', 'From Party',
        ondelete='CASCADE')
    to_party = fields.Many2One('party.party', 'To Party',
        ondelete='CASCADE')
    kind = fields.Selection('get_relation_kind', 'Kind')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    reverse_kind = fields.Function(
        fields.Selection('get_relation_kind', 'Kind'),
        'get_reverse_kind')

    @staticmethod
    def get_relation_kind():
        return PartyRelationKind.get_values_as_selection(
            'party.party_relation_kind')

    @staticmethod
    def default_start_date():
        return datetime.datetime.today()

    def get_reverse_kind(self, name=None):
        RelationKind = Pool().get('party.party_relation_kind')
        relation, = RelationKind.search([('key', '=', self.kind)], limit=1)
        if relation:
            reverse_relation = relation.get_reverse_relation()
            if reverse_relation:
                return reverse_relation.key
