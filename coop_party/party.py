#-*- coding:utf-8 -*-
from trytond.model import fields
from trytond.pyson import Eval, Bool, Not

from trytond.pool import PoolMeta, Pool

from trytond.modules.coop_utils import CoopView, CoopSQL
from trytond.modules.coop_utils import TableOfTable, utils
from trytond.modules.coop_utils import coop_string


__all__ = ['Party', 'Society', 'Employee', 'Actor', 'Person',
           'GenericActorKind', 'GenericActor', 'ACTOR_KIND']

GENDER = [
    ('M', 'Mr.'),
    ('F', 'Mrs.'),
]

ACTOR_KIND = [
    ('party.person', 'Person'),
    ('party.society', 'Society')
]


class Party:
    'Party'

    __name__ = 'party.party'
    __metaclass__ = PoolMeta

    person = fields.One2Many('party.person', 'party', 'Person', size=1,
        states={'invisible': Not(Bool(Eval('person')))})
    society = fields.One2Many('party.society',
        'party', 'Society', size=1,
        states={'invisible': Not(Bool(Eval('society')))})
    employee_role = fields.One2Many('party.employee', 'party', 'Employee',
        size=1)
    generic_roles = fields.One2Many('party.generic_actor', 'party',
        'Generic Actor')
    relations = fields.One2Many('party.party-relation',
        'from_party', 'Relations', context={'direction': 'normal'})
    in_relation_with = fields.One2Many('party.party-relation',
        'to_party', 'in relation with', context={'direction': 'reverse'})
    summary = fields.Function(fields.Text('Summary'), 'get_summary')
    main_address = fields.Function(
        fields.Char('Address'),
        'get_main_address_as_char')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._sql_constraints.remove(('code_uniq', 'UNIQUE(code)',
             'The code of the party must be unique!'))

        #this loop will add for each One2Many role, a function field is_role
        for field_name in dir(cls):
            if not (field_name.endswith('role') or field_name == 'person'
                    or field_name == 'society'):
                continue
            field = getattr(cls, field_name)
            if not hasattr(field, 'model_name'):
                continue
            is_actor_var_name = Party.get_is_actor_var_name(field_name)
            searcher = None
            if not field_name.endswith('_role'):
                searcher = 'search_is_actor'
            field = fields.Function(
                fields.Boolean(
                    field.string, on_change=[field_name, is_actor_var_name]),
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
                setattr(
                    cls, on_change_method, get_on_change(is_actor_var_name))

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
        if res not in ['person', 'society']:
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
        if getattr(self, is_role) is True and len(getattr(self, role)) == 0:
            res[role]['add'] = [{}]
        elif getattr(self, is_role) is False and len(getattr(self, role)) > 0:
            res[role].setdefault('remove', [])
            res[role]['remove'].append(getattr(self, role)[0].id)
        return res

    @classmethod
    def set_is_actor(cls, parties, name, value):
        pass

    def get_rec_name(self, name):
        if self.person:
            return self.person[0].get_rec_name(name)
        elif self.society:
            return self.society[0].get_rec_name(name)
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
        res = cls.get_summary_header(
            parties, name=name, at_date=at_date, lang=lang)
        for party in parties:
            res[party.id] += coop_string.get_field_as_summary(
                party, 'addresses', True, at_date, lang=lang)
            res[party.id] += coop_string.get_field_as_summary(
                party, 'relations', True, at_date, lang=lang)
            res[party.id] += coop_string.get_field_as_summary(
                party, 'in_relation_with', True, at_date, lang=lang)
            res[party.id] += coop_string.get_field_as_summary(
                party, 'generic_roles', True, at_date, lang=lang)
        return res

    @classmethod
    def get_summary_header(cls, parties, name=None, at_date=None, lang=None):
        res = {}
        persons = []
        societies = []
        person_dict = {}
        society_dict = {}
        for party in parties:
            res[party.id] = "<b>%s</b>\n" % party.get_rec_name(name)
            if party.person:
                persons.append(party.person[0])
                person_dict[party.person[0].id] = party.id
            if party.society:
                societies.append(party.society[0])
                society_dict[party.society[0].id] = party.id
        Person = Pool().get('party.person')
        for pers_id, pers_header in Person.get_summary_header(
                persons, at_date=at_date, lang=lang).iteritems():
            res[person_dict[pers_id]] += pers_header

        Society = Pool().get('party.society')
        for comp_id, comp_header in Society.get_summary_header(
                societies, at_date=at_date, lang=lang).iteritems():
            res[society_dict[comp_id]] += comp_header
        return res

    def get_person(self):
        if self.person:
            return self.person[0]

    def get_society(self):
        if self.society:
            return self.society[0]

    def address_get(self, type=None, at_date=None, kind=None):
        addresses = utils.get_good_versions_at_date(self, 'addresses', at_date)
        for address in addresses:
            if ((not type or getattr(address, type)) and
                    (not kind or address.kind == kind)):
                return address

    def get_main_address_as_char(self, name=None, at_date=None):
        address = self.address_get(at_date=at_date)
        if address:
            return address.get_address_as_char(name)

    @classmethod
    def default_lang(cls):
        return utils.get_user_language()


class Actor(CoopView):
    'Actor'
    _inherits = {'party.party': 'party'}
    __name__ = 'party.actor'

    reference = fields.Char('Reference')
    party = fields.Many2One(
        'party.party', 'Party', required=True, ondelete='CASCADE', select=True)


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

    @classmethod
    def get_possible_actor_kind(cls, vals=None):
        return GenericActorKind.get_values_as_selection(
            'party.generic_actor_kind')

    @classmethod
    def get_summary(cls, actors, name=None, at_date=None, lang=None):
        res = {}
        for actor in actors:
            res[actor.id] = coop_string.get_field_as_summary(
                cls, 'kind', True, at_date, lang=lang)
        return res


class Society(CoopSQL, Actor):
    'Society'

    __name__ = 'party.society'

    parent = fields.Many2One('party.society', 'Parent')
    childs = fields.One2Many('party.society', 'parent', 'Children')
    employees = fields.One2Many('party.employee', 'society', 'Employees')

    @classmethod
    def __setup__(cls):
        super(Society, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def get_summary_header(cls, societies, name=None, at_date=None, lang=None):
        return dict([(society.id, '') for society in societies])


class Employee(CoopSQL, Actor):
    'Employee'

    __name__ = 'party.employee'

    society = fields.Many2One('party.society', 'Society', required=True)


class Person(CoopSQL, Actor):
    'Person'

    __name__ = 'party.person'

    gender = fields.Selection(
        GENDER, 'Gender', required=True, on_change=['gender'])
    first_name = fields.Char('First Name', required=True)
    maiden_name = fields.Char(
        'Maiden Name', states={'readonly': Eval('gender') != 'F'},
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
        return "%s %s %s" % (coop_string.translate_value(self, 'gender'),
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
            res[party.id] += coop_string.get_field_as_summary(party, 'ssn')
            res[party.id] += coop_string.get_field_as_summary(
                party, 'birth_date')
            res[party.id] += coop_string.get_field_as_summary(
                party, 'nationality')
            res[party.id] += coop_string.get_field_as_summary(
                party, 'maiden_name')
        return res

    @classmethod
    def search_rec_name(cls, name, clause):
        if cls.search([('first_name',) + clause[1:]], limit=1):
            return [('first_name',) + clause[1:]]
        if cls.search([('ssn',) + clause[1:]], limit=1):
            return [('ssn',) + clause[1:]]
        return [(cls._rec_name,) + clause[1:]]
