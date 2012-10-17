#-*- coding:utf-8 -*-
import copy

from trytond.model import fields as fields, ModelSQL, ModelView
from trytond.pyson import Eval

from trytond.pool import PoolMeta, Pool

from trytond.modules.coop_utils import CoopView, CoopSQL
from trytond.modules.coop_utils import TableOfTable, utils as utils
from trytond.modules.coop_utils import string as string


__all__ = ['Party', 'Company', 'Employee', 'Actor', 'Person',
           'GenericActorKind', 'GenericActor', 'ACTOR_KIND']
__metaclass__ = PoolMeta

GENDER = [('M', 'Mr.'),
          ('F', 'Mrs.'),
            ]

ACTOR_KIND = [('party.person', 'Person'),
              ('company.company', 'Company')]


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
    relations = fields.One2Many('party.party-relation',
        'from_party', 'Relations', context={'direction': 'normal'})
    in_relation_with = fields.One2Many('party.party-relation',
        'to_party', 'in relation with', context={'direction': 'reverse'})
    summary = fields.Function(fields.Text('Summary'), 'get_summary')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._sql_constraints.remove(('code_uniq', 'UNIQUE(code)',
             'The code of the party must be unique!'))

        #this loop will add for each One2Many role, a function field is_role
        for field_name in dir(cls):
            if not (field_name.endswith('role') or field_name == 'person'
                or field_name == 'company'):
                continue
            field = getattr(cls, field_name)
            if not hasattr(field, 'model_name'):
                continue
            is_actor_var_name = Party.get_is_actor_var_name(field_name)
            searcher = None
            if not field_name.endswith('_role'):
                searcher = 'search_is_actor'
            field = fields.Function(fields.Boolean(field.string,
                    on_change=[field_name, is_actor_var_name]),
                'get_is_actor',
                setter='set_is_actor',
                searcher=searcher)
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
    def get_is_actor_var_name(var_name):
        res = 'is_'
        if var_name.endswith('_role'):
            res += var_name.split('_role')[0]
        else:
            res += var_name
        return res

    @staticmethod
    def get_actor_var_name(var_name):
        res = var_name.split('is_')[1]
        if res not in ['person', 'company']:
            res += '_role'
        return res

    def get_is_actor(self, name):
        field_name = Party.get_actor_var_name(name)
        if hasattr(self, field_name):
            field = getattr(self, field_name)
            return len(field) > 0
        return False

    @classmethod
    def search_is_actor(cls, name, clause):
        field_name = Party.get_actor_var_name(name)
        return [(field_name, ) + tuple(clause[1:])]

    def on_change_generic(self, is_role=''):
        res = {}
        if is_role == '':
            return res
        role = Party.get_actor_var_name(is_role)
        if role == '' or is_role == '':
            return res
        res[role] = {}
        if type(getattr(self, role)) == bool:
            return res
        if getattr(self, is_role) == True and len(getattr(self, role)) == 0:
            res[role]['add'] = [{}]
        elif getattr(self, is_role) == False and len(getattr(self, role)) > 0:
            res[role].setdefault('remove', [])
            res[role]['remove'].append(getattr(self, role)[0].id)
        return res

    @classmethod
    def set_is_actor(cls, parties, name, value):
        pass

    def get_rec_name(self, name):
        if self.person:
            return self.person[0].get_rec_name(name)
        elif self.company:
            return self.company[0].get_rec_name(name)
        return super(Party, self).get_rec_name(name)

    def get_nationality(self):
        pass

    def get_subscribed_contracts(self):
        Contract = Pool().get('ins_contract.contract')
        return Contract.search(['subscriber', '=', self.id])

    def get_relation_with(self, target):
        kind = set([elem.kind for elem in self.relations
            if elem.to_party.id == elem.id])
        if kind:
            return kind[0]
        return None

    @classmethod
    def get_summary(cls, parties, name=None, at_date=None, lang=None):
        if not lang:
            lang = utils.get_user_language()
        res = cls.get_summary_header(parties, name=name, at_date=at_date,
            lang=lang)
        for party in parties:
            res[party.id] += string.get_field_as_summary(party, 'addresses',
                True, at_date, lang=lang)
            res[party.id] += string.get_field_as_summary(party, 'relations',
                True, at_date, lang=lang)
            res[party.id] += string.get_field_as_summary(party,
                'in_relation_with', True, at_date, lang=lang)
            res[party.id] += string.get_field_as_summary(party,
                'generic_roles', True, at_date, lang=lang)
        return res

    @classmethod
    def get_summary_header(cls, parties, name=None, at_date=None, lang=None):
        res = {}
        persons = []
        companies = []
        person_dict = {}
        company_dict = {}
        for party in parties:
            res[party.id] = "<b>%s</b>\n" % party.get_rec_name(name)
            if party.person and len(party.person) > 0:
                persons.append(party.person[0])
                person_dict[party.person[0].id] = party.id
            if party.company and len(party.company) > 0:
                companies.append(party.company[0])
                company_dict[party.company[0].id] = party.id
        Person = Pool().get('party.person')
        for pers_id, pers_header in Person.get_summary_header(persons,
            at_date=at_date, lang=lang).iteritems():
            res[person_dict[pers_id]] += pers_header

        Company = Pool().get('company.company')
        for comp_id, comp_header in Company.get_summary_header(companies,
            at_date=at_date, lang=lang).iteritems():
            res[company_dict[comp_id]] += comp_header
        return res


class Company(ModelSQL, ModelView):
    'Company'
    __name__ = 'company.company'

    @classmethod
    def __setup__(cls):
        super(Company, cls).__setup__()
        cls.currency = copy.copy(cls.currency)
        cls.currency.required = False
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def get_summary_header(cls, companies, name=None, at_date=None, lang=None):
        return dict([(company.id, '') for company in companies])


class Employee(ModelSQL, ModelView):
    'Employee'
    __name__ = 'company.employee'

    @classmethod
    def __setup__(cls):
        super(Employee, cls).__setup__()
        cls.party = copy.copy(cls.party)
        if not cls.party.domain:
            cls.party.domain = []
        cls.party.domain.append([('is_person', '=', True)])

    @staticmethod
    def default_person():
        return [{}]


class Actor(CoopView):
    'Actor'
    _inherits = {'party.party': 'party'}
    __name__ = 'party.actor'

    reference = fields.Char('Reference')
    party = fields.Many2One('party.party', 'Party',
                    required=True, ondelete='CASCADE', select=True)


class GenericActorKind(TableOfTable):
    'Generic Actor Kind'

    __name__ = 'party.generic_actor_kind'
    _table = 'coop_table_of_table'

    @staticmethod
    def get_class_where_used():
        return [('party.generic_actor', 'kind')]


class GenericActor(CoopSQL, Actor):
    'Generic Actor'

    __name__ = 'party.generic_actor'

    kind = fields.Selection('get_possible_actor_kind', 'Kind', required=True)

    @staticmethod
    def get_possible_actor_kind():
        return GenericActorKind.get_values_as_selection(
            'party.generic_actor_kind')

    @classmethod
    def get_summary(cls, actors, name=None, at_date=None, lang=None):
        res = {}
        for actor in actors:
            res[actor.id] = string.get_field_as_summary(self, 'kind', True,
                at_date, lang=lang)
        return res


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
    nationality = fields.Many2One(
        'country.country',
        'Nationality')

    @classmethod
    def __setup__(cls):
        super(Person, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    def get_rec_name(self, name):
        return "%s %s %s" % (string.translate_value(self, 'gender'),
            self.name.upper(), self.first_name)

    def on_change_gender(self):
        res = {}
        if self.gender == 'F':
            return res
        res['maiden_name'] = ''
        return res

    @staticmethod
    def gender_as_int(gender):
        return utils.tuple_index(gender, GENDER) + 1

    def get_gender_as_int(self):
        return self.gender_as_int(self.gender)

    def get_nationality(self):
        return self.nationality

    @classmethod
    def get_summary_header(cls, persons, name=None, at_date=None, lang=None):
        res = {}
        for party in persons:
            res[party.id] = ''
            res[party.id] += string.get_field_as_summary(party, 'ssn')
            res[party.id] += string.get_field_as_summary(party, 'birth_date')
            res[party.id] += string.get_field_as_summary(party, 'nationality')
            res[party.id] += string.get_field_as_summary(party, 'maiden_name')
        return res

    @classmethod
    def search_rec_name(cls, name, clause):
        if cls.search([('first_name',) + clause[1:]], limit=1):
            return [('first_name',) + clause[1:]]
        if cls.search([('ssn',) + clause[1:]], limit=1):
            return [('ssn',) + clause[1:]]
        return [(cls._rec_name,) + clause[1:]]
