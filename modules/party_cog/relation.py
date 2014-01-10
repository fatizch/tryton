#-*- coding:utf-8 -*-
from trytond.pyson import Bool, Eval
from trytond.transaction import Transaction

from trytond.modules.cog_utils import model
from trytond.modules.cog_utils import utils, coop_string, fields

__all__ = [
    'PartyRelationKind',
    'PartyRelation',
    ]


class PartyRelationKind(model.CoopSQL, model.CoopView):
    'Party Relation Kind'

    __name__ = 'party.relation.kind'

    code = fields.Char('Code', required=True,
        states={'readonly': Bool(Eval('is_used'))},
        on_change_with=['code', 'name'])
    name = fields.Char('Name', required=True, translate=True)
    reversed_name = fields.Char('Reversed Name', translate=True)

    @classmethod
    def __setup__(cls):
        super(PartyRelationKind, cls).__setup__()
        cls._sql_constraints += [
            ('key_uniq', 'UNIQUE(code)', 'The key must be unique!'),
            ]

    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)


class PartyRelation(model.CoopSQL, model.CoopView):
    'Party Relation'

    __name__ = 'party.relation'
    _rec_name = 'to_party'

    from_party = fields.Many2One('party.party', 'From Party',
        ondelete='CASCADE')
    to_party = fields.Many2One('party.party', 'To Party',
        ondelete='CASCADE')
    relation_kind = fields.Many2One('party.relation.kind',
        'Relation Kind', ondelete='RESTRICT', required=True)
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    relation_name = fields.Function(
        fields.Char('Relation Name',
            on_change_with=['relation_kind']),
        'on_change_with_relation_name')
    kind = fields.Char('Temporary kind for migration use, to be deleted')

    @staticmethod
    def default_start_date():
        return utils.today()

    def on_change_with_relation_name(self, name=None):
        if not self.relation_kind:
            return
        direction = 'normal'
        if 'direction' in Transaction().context:
            direction = Transaction().context['direction']
        if direction == 'normal':
            return self.relation_kind.name
        elif direction == 'reverse':
            return self.relation_kind.reversed_name

    @classmethod
    def get_summary(cls, relations, name=None, at_date=None, lang=None):
        res = {}
        for relation in relations:
            party = relation.to_party
            if not relation.relation_kind:
                relation_name = ''
            elif name == 'in_relation_with':
                relation_name = coop_string.translate_value(
                    relation.relation_kind, 'reversed_name', lang=lang)
                party = relation.from_party
            elif relation.relation_kind:
                relation_name = coop_string.translate_value(
                    relation.relation_kind, 'name', lang=lang)
            res[relation.id] = '%s %s' % (relation_name,
                party.rec_name if party else '')
        return res

    def get_rec_name(self, name):
        return self.get_summary([self], name)[self.id]

    @classmethod
    def get_var_names_for_full_extract(cls):
        return [('to_party', 'light'), ('relation_kind', 'light')]
