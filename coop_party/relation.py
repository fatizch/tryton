#-*- coding:utf-8 -*-
from trytond.model import fields as fields
from trytond.pool import Pool
from trytond.modules.coop_utils import CoopView, CoopSQL, TableOfTable
from trytond.modules.coop_utils import utils as utils

__all__ = ['PartyRelationKind', 'PartyRelation']


class PartyRelationKind(TableOfTable):
    'Party Relation Kind'

    __name__ = 'party.party_relation_kind'
    _table = 'coop_table_of_table'

    @classmethod
    def __setup__(cls):
        super(PartyRelationKind, cls).__setup__()
        cls._sql_constraints += [
            ('key_uniq', 'UNIQUE(key)', 'The key must be unique!'),
        ]

    def get_reverse_relation_kind(self):
        if self.parent:
            return self.parent
        if self.childs and len(self.childs) > 0:
            return self.childs[0]
        #if not children and no parent, the relation is symmetrical ex: spouse
        return self


class PartyRelation(CoopSQL, CoopView):
    'Party Relation'

    __name__ = 'party.party-relation'

    from_party = fields.Many2One('party.party', 'From Party',
        ondelete='CASCADE',
#        states={'invisible':
#            Eval('context', {}).get('direction') != 'reverse'},
        )
    to_party = fields.Many2One('party.party', 'To Party',
        ondelete='CASCADE',
#        states={'invisible':
#            Eval('context', {}).get('direction') != 'normal'},
        )
    kind = fields.Selection('get_relation_kind', 'Kind',
#        states={'invisible':
#            Eval('context', {}).get('direction') != 'normal'},
        )
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    reverse_kind = fields.Function(
        fields.Selection('get_relation_kind', 'Kind',
#            states={'invisible':
#                Eval('context', {}).get('direction') != 'reverse'},
        ), 'get_reverse_kind')

    @staticmethod
    def get_relation_kind():
        return PartyRelationKind.get_values_as_selection(
            'party.party_relation_kind')

    @staticmethod
    def default_start_date():
        return utils.today()

    def get_reverse_kind(self, name=None):
        RelationKind = Pool().get('party.party_relation_kind')
        relation_kind, = RelationKind.search([('key', '=', self.kind)],
            limit=1)
        if relation_kind:
            reverse_relation_kind = relation_kind.get_reverse_relation_kind()
            if reverse_relation_kind:
                return reverse_relation_kind.key

    def get_summary(self, name=None, indent=None, at_date=None):
        if name == 'relations':
            link = 'kind'
            party = self.to_party
        elif name == 'in_relation_with':
            link = 'reverse_kind'
            party = self.from_party
        return utils.re_indent_text(
            '%s %s' % (utils.translate_value(self, link),
                    party.get_rec_name(name)),
            indent)
