#-*- coding:utf-8 -*-
from trytond.pyson import Eval, Bool, Less

from trytond.pool import PoolMeta

from trytond.modules.cog_utils import utils, fields, model, export
from trytond.modules.cog_utils import coop_string


__metaclass__ = PoolMeta
__all__ = [
    'Party',
    ]

GENDER = [
    ('male', 'Mr.'),
    ('female', 'Mrs.'),
    ('', ''),
    ]

STATES_PERSON = Bool(Eval('is_person'))
STATES_COMPANY = Bool(Eval('is_company'))


class Party(export.ExportImportMixin):
    __name__ = 'party.party'

    is_person = fields.Boolean('Person')
    is_company = fields.Boolean('Company')

    relations = fields.One2Many('party.relation', 'from_party', 'Relations',
        context={'direction': 'normal'})
    in_relation_with = fields.One2Many('party.relation', 'to_party',
        'in relation with', context={'direction': 'reverse'})
    summary = fields.Function(fields.Text('Summary'), 'get_summary')
    main_address = fields.Function(
        fields.Many2One('party.address', 'Main Address'),
        'get_main_address_id')
    number_of_addresses = fields.Function(
        fields.Integer('Number Of Addresses', on_change_with=['addresses'],
            states={'invisible': True}),
        'on_change_with_number_of_addresses')
    main_contact_mechanism = fields.Function(
        fields.Many2One('party.contact_mechanism', 'Main Contact Mechanism',
            states={'invisible': ~Eval('main_contact_mechanism')}),
        'get_main_contact_mechanism_id')
    number_of_contact_mechanisms = fields.Function(
        fields.Integer('Number Of Contact Mechanisms',
            on_change_with=['contact_mechanisms'], states={'invisible': True}),
        'on_change_with_number_of_contact_mechanisms')
    ####################################
    #Person information
    gender = fields.Selection(GENDER, 'Gender', on_change=['gender'], states={
            'invisible': ~STATES_PERSON,
            'required': STATES_PERSON,
            })
    first_name = fields.Char('First Name', states={
            'invisible': ~STATES_PERSON,
            'required': STATES_PERSON,
            })
    maiden_name = fields.Char('Maiden Name', states={
            'readonly': Eval('gender') != 'female',
            'invisible': ~STATES_PERSON
            })
    birth_date = fields.Date('Birth Date', states={
            'invisible': ~STATES_PERSON,
            'required': STATES_PERSON,
            })
    ssn = fields.Char('SSN', states={'invisible': ~STATES_PERSON})
    ####################################
    #Company information
    short_name = fields.Char('Short Name',
        states={'invisible': ~STATES_COMPANY},
        depends=['is_company'])
    parent = fields.Many2One('party.party', 'Parent',
        states={'invisible': ~STATES_COMPANY})
    children = fields.One2Many('party.party', 'parent', 'Children',
        states={'invisible': ~STATES_COMPANY})
    logo = fields.Binary('Logo', states={'invisible': ~STATES_COMPANY})
    ####################################

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._buttons.update({
                'open_addresses': {
                    'invisible': Less(Eval('number_of_addresses', 0), 1, True),
                    },
                'open_contact_mechanisms': {
                    'invisible': Less(Eval('number_of_contact_mechanisms', 0),
                        1, True),
                    },
                })

        #this loop will add for each One2Many role, a function field is_role
        for field_name in dir(cls):
            if not field_name.endswith('role'):
                continue
            field = getattr(cls, field_name)
            if not hasattr(field, 'model_name'):
                continue
            is_actor_var_name = Party.get_is_actor_var_name(field_name)
            field = fields.Function(
                fields.Boolean(
                    field.string, on_change=[field_name, is_actor_var_name],
                    states=field.states),
                'get_is_actor', setter='set_is_actor',
                searcher='search_is_actor')
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

    @classmethod
    def _export_keys(cls):
        return set(['name'])

    @classmethod
    def _export_skips(cls):
        res = super(Party, cls)._export_skips()
        res.add('code')
        res.add('code_length')
        return res

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
        if clause[2] is True:
            clause[1], clause[2] = ('!=', None)
        elif clause[2] is False:
            clause[2] = None
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

    def get_clean_name(self):
        if self.is_person:
            res = "%s %s %s" % (coop_string.translate_value(
                self, 'gender'), self.name.upper(), self.first_name)
        return res

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

    def get_relation_with(self, target, at_date=None):
        if not at_date:
            at_date = utils.today()
        kind = [rel.relation_kind.name for rel in
            utils.get_good_versions_at_date(self, 'relations', at_date)
            if rel.to_party.id == target.id]
        kind += [rel.relation_kind.reversed_name for rel in
            utils.get_good_versions_at_date(self, 'in_relation_with', at_date)
            if rel.from_party.id == target.id]
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
            #res[party.id] += coop_string.get_field_as_summary(
            #    party, 'extra_data', True, at_date, lang=lang)
            res[party.id] += coop_string.get_field_as_summary(
                party, 'addresses', True, at_date, lang=lang)
            res[party.id] += coop_string.get_field_as_summary(
                party, 'relations', True, at_date, lang=lang)
            res[party.id] += coop_string.get_field_as_summary(
                party, 'in_relation_with', True, at_date, lang=lang)
        return res

    @classmethod
    def search_rec_name(cls, name, clause):
        parties = cls.search(['OR',
                [('first_name',) + tuple(clause[1:])],
                [('name',) + tuple(clause[1:])],
                [('ssn',) + tuple(clause[1:])]
                ], order=[])
        if parties:
            return [('id', 'in', [party.id for party in parties])]
        return super(Party, cls).search_rec_name(name, clause)

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

    def get_main_address_id(self, name=None, at_date=None):
        address = self.address_get(at_date=at_date)
        return address.id if address else None

    @classmethod
    def default_lang(cls):
        return utils.get_user_language().id

    def on_change_gender(self):
        res = {}
        if self.gender == 'female':
            return res
        res['maiden_name'] = ''
        return res

    @classmethod
    def get_var_names_for_full_extract(cls):
        res = super(Party, cls).get_var_names_for_full_extract()
        res.extend(['is_person', 'is_company', 'relations',
            'gender', 'first_name', 'maiden_name', 'birth_date', 'ssn',
            'short_name', 'addresses', 'contact_mechanisms',
            ('lang', 'light')])
        return res

    def get_main_contact_mechanism_id(self, name):
        return (self.contact_mechanisms[0].id
            if self.contact_mechanisms else None)

    @classmethod
    @model.CoopView.button_action('party_cog.act_addresses_button')
    def open_addresses(cls, objs):
        pass

    @classmethod
    @model.CoopView.button_action('party_cog.act_contact_mechanisms_button')
    def open_contact_mechanisms(cls, objs):
        pass

    def on_change_with_number_of_addresses(self, name=None):
        return len(self.addresses)

    def on_change_with_number_of_contact_mechanisms(self, name=None):
        return len(self.contact_mechanisms)

    @staticmethod
    def default_number_of_contact_mechanisms():
        return 0
