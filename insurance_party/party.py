#-*- coding:utf-8 -*-

from trytond.model import ModelView, ModelSQL, fields as fields
from trytond.pyson import Eval

from trytond.modules.coop_utils import utils as utils

__all__ = ['Party', 'Actor', 'PersonRelations', 'Person', 'LegalEntity',
           'Insurer', ]

GENDER = [('M', 'Male'),
          ('F', 'Female'),
            ]


class Party(ModelSQL, ModelView):
    'Party'
    __name__ = 'party.party'

    person = fields.One2Many('party.person', 'party', 'Person')
    legal_entity = fields.One2Many('party.legal_entity',
                                   'party', 'Legal Entity')
    insurer = fields.One2Many('party.insurer', 'party', 'Insurer',
        states={'invisible': Eval('legal_entity', 0) != 0})

    is_legal_entity = fields.Function(fields.Boolean('Legal entity'),
                                      'get_is_actor')
    is_insurer = fields.Function(fields.Boolean('Insurer',
                                                on_change=['is_insurer',
                                                           'insurer']),
                                 'get_is_actor', setter='set_is_insurer')

    def get_is_actor(self, name):
        field_name = name.split('is_')[2]
        if hasattr(self, field_name):
            field = getattr(self, field_name)
            return len(field) > 0
        return False

    def on_change_is_insurer(self):
        res = {}
        res['insurer'] = {}
        if type(self.insurer) == bool:
            return res
        if self.is_insurer == True and len(self.insurer) == 0:
            res['insurer']['add'] = [{}]
        elif self.is_insurer == False and len(self.insurer) > 0:
            res['insurer'].setdefault('remove', [])
            res['insurer']['remove'].append(self.insurer[0].get('id'))
        return res


class Actor(ModelView):
    'Actor'
    _inherits = {'party.party': 'party'}
    __name__ = 'party.actor'
    _rec_name = 'reference'

    reference = fields.Char('Reference')
    party = fields.Many2One('party.party', 'Party',
                    required=True, ondelete='CASCADE', select=True)


class PersonRelations(ModelSQL, ModelView):
    'Person Relations'

    __name__ = 'party.person-relations'

    from_person = fields.Many2One('party.person', 'From Person')
    to_person = fields.Many2One('party.person', 'From Person')
    kind = fields.Selection('get_relation_kind', 'Kind')
    reverse_kind = fields.Function(fields.Char('Reverse Kind', readonly=True),
                                   'get_reverse_kind')

    @staticmethod
    def get_relation_kind():
        return utils.get_dynamic_selection('person_relation')

    def get_reverse_kind(self, name):
        reverse_values = utils.get_reverse_dynamic_selection(self.kind)
        if len(reverse_values) > 0:
            return reverse_values[0][1]
        return ''


class Person(ModelSQL, Actor):
    'Person'

    __name__ = 'party.person'

    gender = fields.Selection(GENDER, 'Gender', required=True)
    first_name = fields.Char('First Name', required=True)
    maiden_name = fields.Char('Maiden Name',
        states={'invisible': Eval('gender') != 'F'},
        depends=['gender'])
    birth_date = fields.Date('Birth Date', required=True)
    ssn = fields.Char('Social Security Number')
    relations = fields.One2Many('party.person-relations',
                                 'from_person', 'Relations')
    in_relation_with = fields.One2Many('party.person-relations',
                                 'to_person', 'in relation with')

    def get_rec_name(self, name):
        return "%s %s" % self.name.upper(), self.first_name


class LegalEntity(ModelSQL, Actor):
    'Legal Entity'

    __name__ = 'party.legal_entity'


class Insurer(ModelSQL, Actor):
    'Insurer'

    __name__ = 'party.insurer'
