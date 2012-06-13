#-*- coding:utf-8 -*-

from trytond.model import ModelView, ModelSQL, fields as fields
from trytond.pyson import Eval
from trytond.pool import Pool

from trytond.modules.coop_utils import utils as utils

__all__ = ['Party', 'Actor', 'PersonRelations', 'Person', 'LegalEntity',
           'Insurer', 'Broker', ]

GENDER = [('M', 'Male'),
          ('F', 'Female'),
            ]


class Party(ModelSQL, ModelView):
    'Party'

    __name__ = 'party.party'

    person = fields.One2Many('party.person', 'party', 'Person')
    legal_entity = fields.One2Many('party.legal_entity',
        'party', 'Legal Entity')
    is_legal_entity = fields.Function(fields.Boolean('Legal entity'),
        'get_is_actor')

    insurer_role = fields.One2Many('party.insurer', 'party', 'Insurer',
        states={'invisible': Eval('legal_entity', 0) != 0})
    broker_role = fields.One2Many('party.broker', 'party', 'Broker',
        states={'invisible': Eval('legal_entity', 0) != 0})

    @staticmethod
    def get_is_actor_var_name(var_name):
        return 'is_' + var_name.split('_role')[0]

    @staticmethod
    def get_actor_var_name(var_name):
        return var_name.split('is_')[1] + '_role'

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        #this loop will add for each One2Many role, a function field is_role
        for field_name in (role for role in dir(cls) if role.endswith('role')):
            field = getattr(cls, field_name)
            if not hasattr(field, 'model_name'):
                continue
            is_actor_var_name = Party.get_is_actor_var_name(field_name)
            field = fields.Function(fields.Boolean(field.string,
                    on_change=[field_name, is_actor_var_name]),
                'get_is_actor',
                setter='set_is_actor')
            setattr(cls, is_actor_var_name, field)

    def get_is_actor(self, name):
        field_name = Party.get_actor_var_name(name)
        if hasattr(self, field_name):
            field = getattr(self, field_name)
            return len(field) > 0
        return False

    def _change_is_actor(self, role):
        res = {}
        res[role] = {}
        attr_role = getattr(self, role)
        attr_is_role = getattr(self, Party.get_is_actor_var_name(role))
        if type(attr_role) == bool:
            return res
        if attr_is_role == True and len(attr_role) == 0:
            res[role]['add'] = [{}]
        elif attr_is_role == False and len(attr_role) > 0:
            res[role].setdefault('remove', [])
            res[role]['remove'].append(attr_role[0].id)
        return res

    def on_change_is_insurer(self):
        return self._change_is_actor('insurer_role')

    def on_change_is_broker(self):
        return self._change_is_actor('broker_role')

    @classmethod
    def set_is_actor(cls, parties, name, value):
        pass


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
    reverse_kind = fields.Function(fields.Char('Reverse Kind',
            readonly=True,
            on_change_with=['kind']),
        'get_reverse_kind')

    @staticmethod
    def get_relation_kind():
        return utils.get_dynamic_selection('person_relation')

    def get_reverse_kind(self, name):
        reverse_values = utils.get_reverse_dynamic_selection(self.kind)
        if len(reverse_values) > 0:
            return reverse_values[0][1]
        return ''

    def on_change_with_reverse_kind(self, name):
        return self.get_reverse_kind(name)


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


class Broker(ModelSQL, Actor):
    'Broker'

    __name__ = 'party.broker'
