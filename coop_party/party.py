#-*- coding:utf-8 -*-
from trytond.pyson import Eval, Bool

from trytond.pool import PoolMeta

from trytond.modules.coop_utils import CoopView, CoopSQL
from trytond.modules.coop_utils import TableOfTable, utils, fields
from trytond.modules.coop_utils import coop_string


__all__ = [
    'Party',
    'Actor',
    'GenericActorKind',
    'GenericActor',
]

GENDER = [
    ('male', 'Mr.'),
    ('female', 'Mrs.'),
    ('', ''),
]

ACTOR_KIND = [
    ('person', 'Person'),
    ('company', 'Company')
]

STATES_PERSON = Bool(Eval('is_person'))
STATES_COMPANY = Bool(Eval('is_company'))


class Party:
    'Party'

    __name__ = 'party.party'
    __metaclass__ = PoolMeta

    is_person = fields.Boolean('Person')
    is_company = fields.Boolean('Company')

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
    ####################################
    #Person information
    gender = fields.Selection(GENDER, 'Gender',
        on_change=['gender'], states={
            'invisible': ~STATES_PERSON,
            'required': STATES_PERSON,
        })
    first_name = fields.Char('First Name',
        states={
            'invisible': ~STATES_PERSON,
            'required': STATES_PERSON,
        })
    maiden_name = fields.Char('Maiden Name',
        states={
            'readonly': Eval('gender') != 'female',
            'invisible': ~STATES_PERSON
        })
    birth_date = fields.Date('Birth Date',
        states={
            'invisible': ~STATES_PERSON,
            'required': STATES_PERSON,
        })
    ssn = fields.Char('SSN', states={'invisible': ~STATES_PERSON})
    ####################################
    #Company information
    short_name = fields.Char(
        'Short Name', states={'invisible': ~STATES_COMPANY},
        depends=['is_company'])
    parent = fields.Many2One('party.party', 'Parent',
        #domain=[('is_company', '=', True)],
        states={'invisible': ~STATES_COMPANY})
    children = fields.One2Many('party.party', 'parent', 'Children',
        states={'invisible': ~STATES_COMPANY})
    logo = fields.Binary('Logo', states={'invisible': ~STATES_COMPANY})
    ####################################

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))

        #this loop will add for each One2Many role, a function field is_role
        for field_name in dir(cls):
            if not field_name.endswith('role'):
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
                    field.string, on_change=[field_name, is_actor_var_name],
                    states=field.states),
                'get_is_actor', setter='set_is_actor', searcher=searcher)
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
        return res

    @staticmethod
    def get_actor_var_name(var_name):
        return var_name.split('is_')[1] + '_role'

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
        if getattr(self, is_role) and not getattr(self, role):
            res[role]['add'] = [{}]
        elif not getattr(self, is_role) and getattr(self, role):
            res[role].setdefault('remove', [])
            res[role]['remove'].append(getattr(self, role)[0].id)
        return res

    @classmethod
    def set_is_actor(cls, parties, name, value):
        pass

    def get_rec_name(self, name):
        res = ''
        if self.is_person:
            res = "%s %s %s" % (coop_string.translate_value(
                self, 'gender'), self.name.upper(), self.first_name)
            if self.ssn:
                res += ' (%s)' % self.ssn
        if self.is_company:
            res = super(Party, self).get_rec_name(name)
        if res:
            return res
        return super(Party, self).get_rec_name(name)

    def get_relation_with(self, target):
        kind = set([elem.kind for elem in self.relations
            if elem.to_party.id == elem.id])
        if kind:
            return kind[0]
        return None

    @staticmethod
    def gender_as_int(gender):
        return utils.tuple_index(gender, GENDER) + 1

    def get_gender_as_int(self):
        return self.gender_as_int(self.gender)

    @classmethod
    def get_summary(cls, parties, name=None, at_date=None, lang=None):
        if not lang:
            lang = utils.get_user_language()
        res = {}
        for party in parties:
            res[party.id] = "<b>%s</b>\n" % party.get_rec_name(name)
            if party.is_person:
                res[party.id] = coop_string.get_field_as_summary(party, 'ssn')
                res[party.id] += coop_string.get_field_as_summary(
                    party, 'birth_date')
                res[party.id] += coop_string.get_field_as_summary(
                    party, 'maiden_name')
            if party.is_company:
                pass
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
    def search_rec_name(cls, name, clause):
        if cls.search([('first_name',) + clause[1:]], limit=1):
            return [('first_name',) + clause[1:]]
        if cls.search([('ssn',) + clause[1:]], limit=1):
            return [('ssn',) + clause[1:]]
        return [(cls._rec_name,) + clause[1:]]

    def get_person(self):
        if self.is_person:
            return self

    def get_company(self):
        if self.is_company:
            return self.company

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
        return utils.get_user_language().id

    def on_change_gender(self):
        res = {}
        if self.gender == 'female':
            return res
        res['maiden_name'] = ''
        return res


class Actor(CoopView):
    'Actor'
    __name__ = 'party.actor'

    reference = fields.Char('Reference')
    party = fields.Many2One(
        'party.party', 'Party', required=True, ondelete='CASCADE', select=True)

    def get_rec_name(self, name):
        if self.party:
            return self.party.rec_name
        return super(Actor, self).get_rec_name(name)


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
    def get_summary(cls, parties, name=None, at_date=None, lang=None):
        res = {}
        for party in parties:
            res[party.id] = coop_string.get_field_as_summary(
                party, 'kind', True, at_date, lang=lang)
        return res
