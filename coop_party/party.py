#-*- coding:utf-8 -*-
import copy

from trytond.model import fields as fields, ModelSQL, ModelView
from trytond.pyson import Eval

from trytond.pool import PoolMeta

from trytond.modules.coop_utils import CoopView, CoopSQL
from trytond.modules.coop_utils import TableOfTable, DynamicSelection

__all__ = ['Party', 'Company', 'Employee', 'Actor', 'Person',
           'PersonRelations', 'GenericActorKind', 'GenericActor', ]
__metaclass__ = PoolMeta

GENDER = [('M', 'Mr.'),
          ('F', 'Mrs.'),
            ]


class Party:
    'Party'

    __name__ = 'party.party'

    person = fields.One2Many('party.person', 'party', 'Person', size=1)
    company = fields.One2Many('company.company',
        'party', 'Company', size=1)
    employee_role = fields.One2Many('company.employee', 'party', 'Employee',
        size=1)
    generic_roles = fields.One2Many('party.generic_actor', 'party',
        'Generic Actor')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._sql_constraints.remove(('code_uniq', 'UNIQUE(code)',
             'The code of the party must be unique!'))

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

            def get_on_change(name):
                # Use a method to create a new context different of the loop
                def on_change(self):
                    return self.on_change_generic(name)
                return on_change

            on_change_method = 'on_change_%s' % is_actor_var_name
            if not getattr(cls, on_change_method, None):
                setattr(cls, on_change_method,
                    get_on_change(is_actor_var_name))

    @staticmethod
    def default_addresses():
        #RSE 03/07/2012 Temporary fix for xml import. See issue B-529
        return ''

    @staticmethod
    def get_is_actor_var_name(var_name):
        return 'is_' + var_name.split('_role')[0]

    @staticmethod
    def get_actor_var_name(var_name):
        return var_name.split('is_')[1] + '_role'

    def get_is_actor(self, name):
        field_name = Party.get_actor_var_name(name)
        if hasattr(self, field_name):
            field = getattr(self, field_name)
            return len(field) > 0
        return False

    def on_change_generic(self, is_role=''):
        res = {}
        if is_role == '':
            return res
        role = Party.get_actor_var_name(is_role)
        if role == '' or is_role == '':
            return res
        res[role] = {}
        if type(self[role]) == bool:
            return res
        if self[is_role] == True and len(self[role]) == 0:
            res[role]['add'] = [{}]
        elif self[is_role] == False and len(self[role]) > 0:
            res[role].setdefault('remove', [])
            res[role]['remove'].append(self[role][0].id)
        return res

    @classmethod
    def set_is_actor(cls, parties, name, value):
        pass


class Company(ModelSQL, ModelView):
    'Company'
    __name__ = 'company.company'

    @classmethod
    def __setup__(cls):
        super(Company, cls).__setup__()
        cls.currency = copy.copy(cls.currency)
        cls.currency.required = False


class Employee(ModelSQL, ModelView):
    'Employee'
    __name__ = 'company.employee'

    @staticmethod
    def default_person():
        return [{}]


class Actor(CoopView):
    'Actor'
    _inherits = {'party.party': 'party'}
    __name__ = 'party.actor'
    _rec_name = 'reference'

    reference = fields.Char('Reference')
    party = fields.Many2One('party.party', 'Party',
                    required=True, ondelete='CASCADE', select=True)


class GenericActorKind(TableOfTable):
    'Generic Actor Kind'

    __name__ = 'party.generic_actor_kind'
    _table = 'coop_table_of_table'

    @staticmethod
    def default_value_kind():
        return 'str'


class GenericActor(CoopSQL, Actor):
    'Generic Actor'

    __name__ = 'party.generic_actor'

    kind = fields.Many2One('party.generic_actor_kind', 'Kind',
        domain=[('my_model_name', '=', 'party.generic_actor_kind'),
                ('parent', '=', False)],
        required=True)


class PersonRelations(CoopSQL, CoopView):
    'Person Relations'

    __name__ = 'party.person-relations'

    from_person = fields.Many2One('party.person', 'From Person',
        ondelete='CASCADE')
    to_person = fields.Many2One('party.person', 'From Person',
        ondelete='CASCADE')
    kind = fields.Selection('get_relation_kind', 'Kind')
    reverse_kind = fields.Function(fields.Char('Reverse Kind',
            readonly=True,
            on_change_with=['kind']),
        'get_reverse_kind')

    @staticmethod
    def get_relation_kind():
        return DynamicSelection.get_dyn_sel('person_relation')

    def get_reverse_kind(self, name):
        reverse_values = DynamicSelection.get_reverse_dyn_sel(self.kind)
        if len(reverse_values) > 0:
            return reverse_values[0][1]
        return ''

    def on_change_with_reverse_kind(self, name):
        return self.get_reverse_kind(name)


class Person(CoopSQL, Actor):
    'Person'

    __name__ = 'party.person'

    gender = fields.Selection(GENDER, 'Gender',
        required=True,
        on_change=['gender'])
    first_name = fields.Char('First Name', required=True)
    maiden_name = fields.Char('Maiden Name',
        states={'readonly': Eval('gender') != 'F'},
        depends=['gender'])
    birth_date = fields.Date('Birth Date', required=True)
    ssn = fields.Char('SSN')
    relations = fields.One2Many('party.person-relations',
                                 'from_person', 'Relations')
    in_relation_with = fields.One2Many('party.person-relations',
                                 'to_person', 'in relation with')

    def get_rec_name(self, name):
        return "%s %s" % (self.name.upper(), self.first_name)

    def on_change_gender(self):
        res = {}
        if self.gender == 'F':
            return res
        res['maiden_name'] = ''
        return res
