#-*- coding:utf-8 -*-

from trytond.model import ModelView, ModelSQL, fields as fields
from trytond.pyson import Eval

from trytond.modules.coop_utils import utils as utils

GENDER = [('M', 'Male'),
            ('F', 'Female'),
            ]


class Party(ModelSQL, ModelView):
    _name = 'party.party'

    person = fields.One2Many('party.person', 'party', 'Person')
    legal_entity = fields.One2Many('party.legal_entity',
                                   'party', 'Legal Entity')
    insurer = fields.One2Many('party.insurer', 'party', 'Insurer',
        states={'invisible': Eval('legal_entity', 0) != 0})

    is_legal_entity = fields.Function(fields.Boolean('Legal entity'),
                                      'get_is_actor')
    is_insurer = fields.Function(fields.Boolean('Insurer',
                                                on_change=['insurer']),
                                 'get_is_actor', setter='set_is_insurer')

    def get_is_actor(self, ids, name):
        res = {}
        field_name = name.split('is_')[2]
        for party in self.browse(ids):
            if hasattr(party, field_name):
                field = getattr(party, field_name)
                res[party.id] = len(field) > 0
        return res

    def set_is_insurer(self, ids, name, value):
        print 'value :', value
        if value:
            self.write(ids, {'insurer': [{}]})

    def on_change_is_insurer(self, vals):
        res = {}
        print 'Is insurer : ', vals.get('is_insurer')
        if vals.get('is_insurer') == True:
            print 'yes'
            res['insurer']['add'] = [{}]
        return res
Party()


class Actor(ModelView):
    _inherits = {'party.party': 'party'}
    _name = 'party.actor'

    party = fields.Many2One('party.party', 'Party',
                    required=True, ondelete='CASCADE', select=True)

Actor()


class PersonRelations(ModelSQL, ModelView):
    'Person Relations'

    _name = 'party.person-relations'
    _description = __doc__

    from_person = fields.Many2One('party.person', 'From Person')
    to_person = fields.Many2One('party.person', 'From Person')
    kind = fields.Selection('get_relation_kind', 'Kind')
    reverse_kind = fields.Function(fields.Char('Reverse Kind', readonly=True),
                                   'get_reverse_kind')

    def get_relation_kind(self):
        return utils.get_dynamic_selection('person_relation')

    def get_reverse_kind(self, ids, name):
        res = {}
        for relation in self.browse(ids):
            reverse_values = utils.get_reverse_dynamic_selection(relation.kind)
            if len(reverse_values) > 0:
                res[relation.id] = reverse_values[0][1]
        return res

PersonRelations()


class Person(ModelSQL, Actor):
    'Person'

    _name = 'party.person'
    _description = __doc__

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

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        for person in self.browse(ids):
                res[person.id] = ("%s %s" %
                                  (person.name.upper(), person.first_name))
        return res
Person()


class LegalEntity(ModelSQL, Actor):
    'Legal Entity'

    _name = 'party.legal_entity'
    _description = __doc__

LegalEntity()


class Insurer(ModelSQL, Actor):
    'Insurer'

    _name = 'party.insurer'
    _description = __doc__

Insurer()
