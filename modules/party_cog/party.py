# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import StringIO
import datetime
import json

from sql.aggregate import Max
from sql import Literal, Cast
from sql.operators import Concat
from sql.conditionals import Coalesce
from sql.functions import Function

from trytond import backend
from trytond.model import Unique
from trytond.pyson import Eval, Bool, Or
from trytond.pool import PoolMeta, Pool
from trytond.tools import grouped_slice, cursor_dict
from trytond.cache import Cache

from trytond.rpc import RPC
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateAction, StateTransition, StateView
from trytond.pyson import PYSONEncoder
from trytond.modules.coog_core import utils, fields, model, export, summary
from trytond.modules.coog_core import coog_string, UnionMixin


__all__ = [
    'Party',
    'PartyLang',
    'PartyIdentifier',
    'PartyIdentifierType',
    'SynthesisMenuAddress',
    'SynthesisMenuPartyInteraction',
    'SynthesisMenuContact',
    'SynthesisMenu',
    'SynthesisMenuOpen',
    'SynthesisMenuOpenState',
    'SynthesisMenuSet',
    'SynthesisMenuActionCloseSynthesis',
    'SynthesisMenuActionRefreshSynthesis',
    'SynthesisMenuRelationship',
    'PartyReplace',
    'PartyReplaceAsk',
    'PartyErase',
    ]

GENDER = [
    ('male', 'Mr.'),
    ('female', 'Mrs.'),
    ('', ''),
    ]

LONG_GENDER = [
    ('male', 'Mister'),
    ('female', 'Madame'),
    ('', ''),
    ]


STATES_PERSON = Bool(Eval('is_person'))
STATES_COMPANY = ~Eval('is_person')
STATES_ACTIVE = ~Eval('active', True)


class Party(export.ExportImportMixin, summary.SummaryMixin):
    __name__ = 'party.party'
    _func_key = 'code'

    summary = fields.Function(fields.Text('Summary'), 'get_summary')
    main_address = fields.Function(
        fields.Many2One('party.address', 'Main Address'),
        'get_main_address_id', searcher='search_main_address')
    has_active_address = fields.Function(
        fields.Boolean('Has Active Address'), 'get_has_active_address')
    all_addresses = fields.One2ManyDomain('party.address', 'party',
        'All Addresses', domain=[('active', 'in', [True, False])],
        target_not_required=True)
    has_multiple_addresses = fields.Function(
        fields.Boolean('Has multiple addresses'),
        'on_change_with_has_multiple_addresses')
    ####################################
    # Person information
    is_person = fields.Boolean('Person', states={'readonly': Or(
                STATES_ACTIVE,
                Bool(Eval('birth_date')),
                Bool(Eval('first_name')))},
        depends=['active', 'birth_date', 'first_name'])
    gender = fields.Selection(GENDER, 'Gender', states={
            'invisible': ~STATES_PERSON,
            'required': STATES_PERSON,
            'readonly': STATES_ACTIVE,
            }, depends=['is_person', 'active'])
    long_gender = fields.Function(
        fields.Selection(LONG_GENDER, 'Gender Long',
            states={'invisible': True}),
        'get_long_gender')
    gender_string = gender.translated('gender')
    long_gender_string = gender.translated('long_gender')
    first_name = fields.Char('First Name', states={
            'invisible': ~STATES_PERSON,
            'required': STATES_PERSON,
            'readonly': STATES_ACTIVE,
            }, depends=['is_person', 'active'])
    birth_name = fields.Char('Birth Name', states={
            'invisible': ~STATES_PERSON,
            'readonly': STATES_ACTIVE,
            }, depends=['is_person', 'active'])
    birth_date = fields.Date('Birth Date', states={
            'invisible': ~STATES_PERSON,
            'readonly': STATES_ACTIVE,
            'required': STATES_PERSON,
            }, depends=['is_person', 'active'])
    ssn = fields.EmptyNullChar('SSN', states={
            'invisible': ~STATES_PERSON,
            'readonly': STATES_ACTIVE,
            'required': Eval('ssn_required', False)
            }, depends=['is_person', 'ssn_required', 'active'])
    ssn_required = fields.Function(fields.Boolean('SSN Required'),
        'get_SSN_required')
    ####################################
    # Company information
    commercial_name = fields.Char('Commercial Name', states={
            'invisible': ~STATES_COMPANY,
            'readonly': STATES_ACTIVE,
            }, depends=['is_person', 'active'])
    logo = fields.Binary('Logo', states={
            'invisible': ~STATES_COMPANY,
            'readonly': STATES_ACTIVE,
            }, depends=['is_person', 'active'])
    ####################################
    synthesis = fields.One2Many('party.synthesis.menu', 'party', 'Synthesis',
        readonly=True)
    synthesis_rec_name = fields.Function(
        fields.Char('Name'), 'get_synthesis_rec_name')
    last_modification = fields.Function(fields.DateTime('Last Modification'),
        'get_last_modification')
    is_anonymized = fields.Boolean('Is Anonymized', readonly=True)

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.8: rename short_name to commercial_name
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)
        if table.column_exist('short_name'):
            table.column_rename('short_name', 'commercial_name')
        if table.column_exist('is_company'):
            table.drop_column('is_company')
        if table.column_exist('parent'):
            table.drop_column('parent')
        if TableHandler.table_exist('party_party__history'):
            table_h = TableHandler(cls, module_name, history=True)
            if table_h.column_exist('short_name'):
                table_h.column_rename('short_name', 'commercial_name')
            if table_h.column_exist('is_company'):
                table_h.drop_column('is_company')
            if table_h.column_exist('parent'):
                table_h.drop_column('parent')

        super(Party, cls).__register__(module_name)

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('SSN_uniq', Unique(t, t.ssn),
             'The SSN of the party must be unique.')
        ]
        cls.name.required = True
        cls._error_messages.update({
                'duplicate_party': ('Duplicate(s) already exist(s) : %s'),
                'invalid_birth_date': ('Birth date can\'t be in the future :'
                    '\n%(name)s - %(birthdate)s'),
                })
        cls.__rpc__.update({'ws_create_person': RPC(readonly=False)})
        cls._buttons.update({
                'button_start_synthesis_menu': {'readonly': STATES_ACTIVE},
                })
        cls._order.insert(0, ('last_modification', 'DESC'))
        for contact_type in ('phone', 'mobile', 'fax', 'email', 'website'):
            contact_field = getattr(cls, contact_type)
            contact_field.setter = 'set_contact'
            contact_field.readonly = False
        cls.full_name.searcher = 'search_full_name'

        cls.relations.states['readonly'] = STATES_ACTIVE
        cls.relations.depends += ['active']
        cls.phone.states['readonly'] = STATES_ACTIVE
        cls.phone.depends += ['active']
        cls.mobile.states['readonly'] = STATES_ACTIVE
        cls.mobile.depends += ['active']
        cls.fax.states['readonly'] = STATES_ACTIVE
        cls.fax.depends += ['active']
        cls.email.states['readonly'] = STATES_ACTIVE
        cls.email.depends += ['active']
        cls.website.states['readonly'] = STATES_ACTIVE
        cls.website.depends += ['active']

    @classmethod
    def view_attributes(cls):
        return super(Party, cls).view_attributes() + [
            ("/form/group[@id='last_name']", 'states',
                {'invisible': ~STATES_PERSON}),
            ("/form//group[@id='label_company_name']", 'states',
                {'invisible': STATES_PERSON}),
            ("/form//group[@id='field_company_name']", 'states',
                {'invisible': STATES_PERSON}),
            ("/form/notebook/page/group[@id='several_addresses']", 'states', {
                    'invisible': ~Eval('has_multiple_addresses', False)}),
            ("/form/notebook/page/group[@id='one_address']", 'states', {
                    'invisible': Eval('has_multiple_addresses', False)}),
            ("/form/group[@id='button']", 'states', {'invisible': True}),
            ]

    @staticmethod
    def default_addresses():
        return None

    @staticmethod
    def default_all_addresses():
        if Transaction().user == 0:
            return []
        return [{}]

    @fields.depends('all_addresses')
    def on_change_with_has_multiple_addresses(self, name=None):
        if not self.all_addresses:
            return False
        return len([x for x in self.all_addresses if x.id > 0]) > 1

    @classmethod
    def add_func_key(cls, values):
        if 'code' in values:
            values['_func_key'] = values['code']
        elif (values.get('name', False) and values.get('first_name', False) and
                values.get('birth_date', False)):
            values['_func_key'] = '%s|%s|%s' % (values['name'],
                values['first_name'], values['birth_date'])
        else:
            super(Party, cls).add_func_key(values)

    def get_func_key(self, name):
        if not self.is_person:
            return self.code
        return '%s|%s|%s' % (self.name, self.first_name, self.birth_date)

    def get_long_gender(self, name):
        return self.gender

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            assert len(operands) == 3
            name, first_name, birth_date = operands
            res = [('is_person', '=', True)]
            if name != 'None':
                res.append(('name', clause[1], name))
            if first_name != 'None':
                res.append(('first_name', clause[1], first_name))
            if birth_date != 'None':
                res.append(('birth_date', clause[1], birth_date))
            return res
        else:
            return ['OR',
                [('code',) + tuple(clause[1:])],
                ]

    @classmethod
    def get_existing_lines(cls, main_object, field_name):
        if field_name == 'relations':
            return dict((getattr(l, l._func_key), l)
                        for l in getattr(main_object, field_name)
                        if not l.id % 2)
        else:
            return super(Party, cls).get_existing_lines(main_object,
                    field_name)

    @classmethod
    def _domain_duplicate_for_person(cls, party):
        return [
            ('id', '!=', party.id),
            ('name', 'ilike', party.name),
            ('first_name', 'ilike', party.first_name),
            ('birth_date', '=', party.birth_date),
            ]

    @classmethod
    def _domain_duplicate_for_company(cls, party):
        return [
            ('id', '!=', party.id),
            ('name', 'ilike', party.name),
            ('commercial_name', 'ilike', party.commercial_name),
            ]

    @classmethod
    def check_duplicates(cls, parties):
        in_max = Transaction().database.IN_MAX
        for i in range(0, len(parties), in_max):
            sub_parties = [p for p in parties[i:i + in_max]]
            domain = ['OR']
            for party in sub_parties:
                if party.is_person:
                    domain.append(cls._domain_duplicate_for_person(party))
                else:
                    domain.append(cls._domain_duplicate_for_company(party))
            if len(domain) == 1:
                continue
            duplicate_parties = cls.search(domain)
            messages = []
            for party in duplicate_parties:
                if party.is_person:
                    messages.append(
                        '%s %s %s \n' % (party.name, party.first_name,
                            Pool().get('ir.date').date_as_string(
                                party.birth_date)))
                else:
                    messages.append('%s %s\n' % (party.name,
                        party.commercial_name))
            if messages:
                cls.raise_user_warning('Duplicate Party', 'duplicate_party',
                    ','.join(messages))

    @classmethod
    def validate(cls, parties):
        super(Party, cls).validate(parties)
        cls.check_duplicates(parties)
        with model.error_manager():
            for party in parties:
                if party.birth_date and party.birth_date > utils.today():
                    cls.append_functional_error('invalid_birth_date', {
                            'name': party.rec_name,
                            'birthdate': party.birth_date})

    @classmethod
    def copy(cls, parties, default=None):
        default = default.copy() if default else {}
        default.setdefault('synthesis', None)
        default.setdefault('first_name', 'temp_for_copy')
        default.setdefault('name', 'temp_for_copy')
        default.setdefault('addresses', [])
        clones = super(Party, cls).copy(parties, default=default)
        for clone, original in zip(clones, parties):
            if original.first_name:
                clone.first_name = '%s_1' % original.first_name
                clone.name = original.name
            else:
                clone.first_name = ''
                clone.name = '%s_1' % original.name
        cls.save(clones)
        return clones

    @staticmethod
    def order_last_modification(tables):
        table, _ = tables[None]
        return [Coalesce(table.write_date, table.create_date)]

    @staticmethod
    def default_gender():
        return ''

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def _export_skips(cls):
        return super(Party, cls)._export_skips() | {
            'code_length', 'synthesis', 'addresses'}

    @classmethod
    def _export_light(cls):
        return super(Party, cls)._export_light() | {
            'lang', 'account_payable', 'account_receivable'}

    @staticmethod
    def get_actor_var_name(var_name):
        return var_name.split('is_')[1] + '_role'

    def get_is_actor(self, name):
        field_name = Party.get_actor_var_name(name)
        if hasattr(self, field_name):
            field = getattr(self, field_name)
            return len(field) > 0
        return False

    def get_SSN_required(self, name):
        return False

    @classmethod
    def search_is_actor(cls, name, clause):
        clause = list(clause)
        if clause[2] is True:
            clause[1], clause[2] = ('!=', None)
        elif clause[2] is False:
            clause[2] = None
        field_name = Party.get_actor_var_name(name)
        return [(field_name, ) + tuple(clause[1:])]

    def _on_change_is_actor(self, name):
        pool = Pool()
        if getattr(self, name, False):
            role_name = self.get_actor_var_name(name)
            field = getattr(self.__class__, role_name)
            Role = pool.get(field.model_name)
            setattr(self, role_name, [Role()])

    @classmethod
    def set_is_actor(cls, parties, name, value):
        if not value:
            field_name = cls.get_actor_var_name(name)
            roles = []
            for party in parties:
                roles.extend(list(getattr(party, field_name)))
            field = getattr(cls, field_name)
            Role = Pool().get(field.model_name)
            Role.delete(roles)

    def get_full_name(self, name):
        if self.is_person:
            return '%s %s %s' % (self.gender_string, self.name.upper(),
                self.first_name)
        return super(Party, self).get_full_name(name)

    def get_rec_name(self, name):
        if Transaction().context.get('company') == self.id:
            return self.name
        else:
            if self.ssn:
                return '[%s] %s - %s' % (self.code, self.full_name, self.ssn)
            else:
                return '[%s] %s' % (self.code, self.full_name)

    def get_synthesis_rec_name(self, name):
        if self.is_person:
            res = '%s %s %s' % (coog_string.translate_value(
                self, 'gender'), self.name.upper(), self.first_name)
            if self.ssn:
                res += ' (%s)' % self.ssn
            if self.birth_date:
                Date = Pool().get('ir.date')
                res += ' (%s)' % Date.date_as_string(self.birth_date)
        else:
            res = self.get_rec_name(name)
        return res

    def get_icon(self, name=None):
        if not self.is_person:
            return 'coopengo-company'
        return 'coopengo-party'

    def get_relation_with(self, target, at_date=None):
        if not at_date:
            at_date = utils.today()
        kind = [rel.type.code for rel in
            utils.get_good_versions_at_date(self, 'relations', at_date)
            if rel.to.id == target.id]
        if kind:
            return kind[0]
        return None

    def get_summary_content(self, label, at_date=None, lang=None):
        if label is True:
            label = self.rec_name
        value = []
        if self.is_person:
            value.append(coog_string.get_field_summary(self, 'ssn', True,
                at_date, lang))
            value.append(coog_string.get_field_summary(self, 'birth_date',
                True, at_date, lang))
            if self.birth_name:
                value.append(coog_string.get_field_summary(self, 'birth_name',
                    True, at_date, lang))
        if self.identifiers:
            value.append(coog_string.get_field_summary(self, 'identifiers',
                True, at_date, lang))
        if self.relations:
            value.append(coog_string.get_field_summary(self, 'relations',
                True, at_date, lang))
        if self.addresses:
            value.append(coog_string.get_field_summary(self, 'addresses', True,
                at_date, lang))
        return (label, value)

    @classmethod
    def search_rec_name(cls, name, clause):
        # TODO : add an index on full_name search
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        domain = [bool_op,
            ('code',) + tuple(clause[1:]),
            ('identifiers.code',) + tuple(clause[1:]),
            ('ssn',) + tuple(clause[1:]),
            ]
        # We do not want to search on full_name for too short strings since the
        # search is rather expensive
        if (not isinstance(clause[2], basestring) or
                ' ' not in clause[2].strip(' %')):
            return domain + [('name',) + tuple(clause[1:])]
        return domain + [('full_name',) + tuple(clause[1:])]

    @classmethod
    def search_full_name(cls, name, clause):
        table = cls.__table__()
        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]
        query = table.select(table.id,
            where=Operator(Concat(table.name, Concat(' ', table.first_name)),
                value) | (Operator(table.name, value)))
        return [('id', 'in', query)]

    def get_person(self):
        if self.is_person:
            return self

    def get_company(self):
        if not self.is_person:
            return self.company

    def address_get(self, type=None, at_date=None):
        # TODO : cache
        pool = Pool()
        Address = pool.get('party.address')
        addresses = utils.get_good_versions_at_date(self, 'addresses', at_date)
        if not addresses:
            if not at_date:
                at_date = utils.today()
            return utils.get_value_at_date([x for x in Address.search(
                        [('party', '=', self.id), ('active', '=', False)])],
                at_date, 'start_date')
        addresses = sorted(addresses, key=lambda x: x.start_date or
            datetime.date.min, reverse=True)
        for address in addresses:
            if not type or getattr(address, type):
                return address
        if addresses:
            return addresses[0]

    def get_main_address_id(self, name=None, at_date=None):
        address = self.address_get(at_date=at_date)
        return address.id if address else None

    def get_has_active_address(self, name=None):
        addresses = utils.get_good_versions_at_date(
            self, 'addresses', utils.today())
        return any([x.active for x in addresses])

    def get_last_modification(self, name):
        return (self.write_date if self.write_date else self.create_date
            ).replace(microsecond=0)

    @classmethod
    def get_identifier(cls, parties, names):
        cursor = Transaction().connection.cursor()
        pool = Pool()
        Identifier = pool.get('party.identifier')
        identifier = Identifier.__table__()
        values = {}
        for name in names:
            values[name] = {x.id: None for x in parties}
        for party_slice in grouped_slice(parties):
            query = identifier.select(
                identifier.party,
                identifier.type,
                identifier.code,
                where=(
                    identifier.type.in_(names)
                    & identifier.party.in_([x.id for x in party_slice])
                    )
                )
            cursor.execute(*query)
            for elem in cursor_dict(cursor):
                values[elem['type']][elem['party']] = elem['code']
        return values

    @classmethod
    def search_main_address(cls, name, clause):
        return [('addresses.rec_name', ) + tuple(clause[1:])]

    @classmethod
    def search_identifier(cls, name, clause):
        return [
            ('identifiers.code',) + tuple(clause[1:]),
            ('identifiers.type', '=', name),
            ]

    @fields.depends('gender')
    def on_change_gender(self):
        if self.gender == 'female':
            return
        self.birth_name = ''

    @classmethod
    def set_contact(cls, parties, name, value):
        pool = Pool()
        Contact = pool.get('party.contact_mechanism')
        contact_to_save = []
        for party in parties:
            for contact in party.contact_mechanisms:
                if contact.type != name:
                    continue
                if value:
                    contact.value = value
                else:
                    contact.active = False
                contact_to_save.append(contact)
                break
            else:
                if value:
                    contact_to_save.append(Contact(type=name,
                            value=value, party=party, active=True))
        Contact.save(contact_to_save)

    def get_publishing_values(self):
        result = super(Party, self).get_publishing_values()
        result['name'] = self.name
        result['first_name'] = self.first_name
        result['birth_date'] = self.birth_date
        result['gender'] = coog_string.translate_value(self, 'gender')
        try:
            result['main_address'] = self.addresses[0]
        except Exception:
            pass
        result['logo'] = StringIO.StringIO(str(self.logo)) if self.logo else ''
        return result

    @classmethod
    def update_create_person_dict(cls, person_dict):
        if person_dict['addresses']:
            for cur_address in person_dict['addresses']:
                if not cur_address['country']:
                    continue
                Country = Pool().get('country.country')
                countries = Country.search([
                    ('code', '=', cur_address['country'])])
                if not countries:
                    return {
                        'return': False,
                        'error_code': 'unknown_country',
                        'error_message': 'No country found for code %s' %
                        cur_address['country'],
                        }
                else:
                    cur_address['country'] = countries[0]
        return person_dict

    @classmethod
    def ws_create_person(cls, person_dict):
        Party = Pool().get('party.party')
        # TODO : USE person constraint
        # if person_dict.get('code', None):
        #     domain = [('code', '=', person_dict['code'])]
        # elif person_dict.get('ssn', None):
        #     domain = [('ssn', '=', person_dict['ssn'])]
        # else:
        #     domain = [('name', '=', person_dict['name']),
        #         ('first_name', '=', person_dict['first_name']),
        #         ('birth_date', '=', person_dict['birth_date'])]
        res = cls.update_create_person_dict(person_dict)
        if not res.get('return', True):
            return res
        party = Party(**res)
        party.is_person = True
        party.save()
        return {'return': True,
            'party_id': party.id,
            'party_code': party.code,
            }

    @classmethod
    @model.CoogView.button_action('party_cog.start_synthesis_menu')
    def button_start_synthesis_menu(cls, parties):
        pass

    @classmethod
    def _import_json(cls, values, main_object=None):
        if 'all_addresses' not in values and 'addresses' in values:
            values['all_addresses'] = []
        return super(Party, cls)._import_json(values, main_object)


class PartyLang(export.ExportImportMixin):
    __metaclass__ = PoolMeta
    __name__ = 'party.party.lang'


class PartyIdentifier(export.ExportImportMixin):
    __name__ = 'party.identifier'
    _func_key = 'code'
    _identifier_type_cache = Cache('party.identifier.get_types', context=False)

    @classmethod
    def __setup__(cls):
        super(PartyIdentifier, cls).__setup__()
        cls.__previous_type_selection = cls.type.selection
        cls.type.selection = 'get_types'
        cls.type.required = True

    @classmethod
    def get_types(cls):
        types = cls._get_base_types()
        lang = Transaction().language
        dyn_types = cls._identifier_type_cache.get(lang)
        if dyn_types is not None:
            return types + dyn_types
        dyn_types = []
        for identifier_type in Pool().get('party.identifier.type').search([]):
            dyn_types.append((identifier_type.code,
                    coog_string.translate_value(identifier_type, 'name')))
        cls._identifier_type_cache.set(lang, dyn_types)
        return types + dyn_types

    @classmethod
    def _get_base_types(cls):
        return cls.__previous_type_selection

    def get_summary_content(self, label, at_date=None, lang=None):
        return (self.type, self.code)


class PartyIdentifierType(model.CoogSQL, model.CoogView):
    'Party Identifier Type'

    __name__ = 'party.identifier.type'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)

    @classmethod
    def __setup__(cls):
        super(PartyIdentifierType, cls).__setup__()
        cls._error_messages.update({
                'type_is_used': 'Identifier type is used. Deletion impossible',
                })

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        return (coog_string.slugify(self.name)
            if self.name and not self.code else self.code)

    @classmethod
    def delete(cls, instances):
        pool = Pool()
        Party = pool.get('party.party')
        if Party.search(
                [('identifiers.type', 'in', [x.code for x in instances])]):
            cls.raise_user_error('type_is_used')
        Pool().get('party.identifier')._identifier_type_cache.clear()
        super(PartyIdentifierType, cls).delete(instances)

    @classmethod
    def create(cls, vlist):
        Pool().get('party.identifier')._identifier_type_cache.clear()
        return super(PartyIdentifierType, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        Pool().get('party.identifier')._identifier_type_cache.clear()
        super(PartyIdentifierType, cls).write(*args)


class SynthesisMenuActionCloseSynthesis(model.CoogSQL):
    'Party Synthesis Menu Action Close'
    __name__ = 'party.synthesis.menu.action_close'
    name = fields.Char('Close Synthesis')
    party = fields.Many2One('party.party', 'Party', ondelete='SET NULL')

    @staticmethod
    def table_query():
        pool = Pool()
        Party = pool.get('party.party')
        party_table = Party.__table__()
        PartyActionClose = pool.get(
            'party.synthesis.menu.action_close')
        User = pool.get('res.user')
        user = Transaction().user
        user = User(user)
        if user.party_synthesis:
            party_id = json.loads(user.party_synthesis)[0]
        else:
            party_id = 0
        return party_table.select(
            Literal(party_id).as_('id'),
            Max(party_table.create_uid).as_('create_uid'),
            Max(party_table.create_date).as_('create_date'),
            Max(party_table.write_uid).as_('write_uid'),
            Max(party_table.write_date).as_('write_date'),
            Literal(coog_string.translate_label(PartyActionClose,
                'name')).as_('name'), Literal(party_id).as_('party'))

    def get_icon(self, name=None):
        return 'coopengo-close'

    def get_rec_name(self, name):
        PartyActionClose = Pool().get('party.synthesis.menu.action_close')
        return coog_string.translate_label(PartyActionClose, 'name')


class SynthesisMenuActionRefreshSynthesis(model.CoogSQL):
    'Party Synthesis Menu Action Refresh'
    __name__ = 'party.synthesis.menu.action_refresh'

    name = fields.Char('Refresh Synthesis')
    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE')

    @staticmethod
    def table_query():
        pool = Pool()
        Party = pool.get('party.party')
        party_table = Party.__table__()
        PartyActionRefresh = pool.get('party.synthesis.menu.action_refresh')
        User = pool.get('res.user')
        user = Transaction().user
        user = User(user)
        if user.party_synthesis:
            party_id = json.loads(user.party_synthesis)[0]
        else:
            party_id = 0
        return party_table.select(
            Literal(party_id).as_('id'),
            Max(party_table.create_uid).as_('create_uid'),
            Max(party_table.create_date).as_('create_date'),
            Max(party_table.write_uid).as_('write_uid'),
            Max(party_table.write_date).as_('write_date'),
            Literal(coog_string.translate_label(PartyActionRefresh,
                'name')).as_('name'), Literal(party_id).as_('party'))

    def get_icon(self, name=None):
        return 'tryton-refresh'

    def get_rec_name(self, name):
        PartyActionRefresh = Pool().get('party.synthesis.menu.action_refresh')
        return coog_string.translate_label(PartyActionRefresh, 'name')


class SynthesisMenuPartyInteraction(model.CoogSQL):
    'Party Synthesis Menu Interaction'
    __name__ = 'party.synthesis.menu.party_interaction'
    name = fields.Char('Interactions')
    party = fields.Many2One('party.party', 'Party', ondelete='SET NULL')

    @staticmethod
    def table_query():
        pool = Pool()
        PartyInteraction = pool.get('party.interaction')
        party_interaction = PartyInteraction.__table__()
        PartyInteractionSynthesis = pool.get(
            'party.synthesis.menu.party_interaction')
        return party_interaction.select(
            party_interaction.party.as_('id'),
            Max(party_interaction.create_uid).as_('create_uid'),
            Max(party_interaction.create_date).as_('create_date'),
            Max(party_interaction.write_uid).as_('write_uid'),
            Max(party_interaction.write_date).as_('write_date'),
            Literal(coog_string.translate_label(PartyInteractionSynthesis,
                'name')).as_('name'),
            party_interaction.party,
            group_by=party_interaction.party)

    def get_rec_name(self, name):
        PartyInteraction = Pool().get('party.synthesis.menu.party_interaction')
        return coog_string.translate_label(PartyInteraction, 'name')


class SynthesisMenuAddress(model.CoogSQL):
    'Party Synthesis Menu Address'
    __name__ = 'party.synthesis.menu.address'
    name = fields.Char('Addresses')
    party = fields.Many2One('party.party', 'Party', ondelete='SET NULL')

    @staticmethod
    def table_query():
        pool = Pool()
        Address = pool.get('party.address')
        AddressSynthesis = pool.get('party.synthesis.menu.address')
        party = pool.get('party.party').__table__()
        address = Address.__table__()
        query_table = party.join(address, 'LEFT OUTER', condition=(
            party.id == address.party))
        return query_table.select(
            party.id,
            Max(address.create_uid).as_('create_uid'),
            Max(address.create_date).as_('create_date'),
            Max(address.write_uid).as_('write_uid'),
            Max(address.write_date).as_('write_date'),
            Literal(coog_string.translate_label(AddressSynthesis, 'name')).
            as_('name'), party.id.as_('party'),
            group_by=party.id)

    def get_icon(self, name=None):
        return 'coopengo-address'

    def get_rec_name(self, name):
        AddressSynthesis = Pool().get('party.synthesis.menu.address')
        return coog_string.translate_label(AddressSynthesis, 'name')


class SynthesisMenuContact(model.CoogSQL):
    'Party Synthesis Menu Contact'
    __name__ = 'party.synthesis.menu.contact'
    name = fields.Char('Contacts')
    party = fields.Many2One('party.party', 'Party', ondelete='SET NULL')

    @staticmethod
    def table_query():
        pool = Pool()
        Contact = pool.get('party.contact_mechanism')
        ContactSynthesis = pool.get('party.synthesis.menu.contact')
        party = pool.get('party.party').__table__()
        contact = Contact.__table__()
        query_table = party.join(contact, 'LEFT OUTER', condition=(
            party.id == contact.party))
        return query_table.select(
            party.id,
            Max(contact.create_uid).as_('create_uid'),
            Max(contact.create_date).as_('create_date'),
            Max(contact.write_uid).as_('write_uid'),
            Max(contact.write_date).as_('write_date'),
            Literal(coog_string.translate_label(ContactSynthesis, 'name')).
            as_('name'), party.id.as_('party'),
            group_by=party.id)

    def get_icon(self, name=None):
        return 'contact'

    def get_rec_name(self, name):
        ContactSynthesis = Pool().get('party.synthesis.menu.contact')
        return coog_string.translate_label(ContactSynthesis, 'name')


class SynthesisMenuRelationship(model.CoogSQL):
    'Party Synthesis Menu Contact'
    __name__ = 'party.synthesis.menu.relationship'
    name = fields.Char('Party Relation')
    party = fields.Many2One('party.party', 'Party', ondelete='SET NULL')

    @staticmethod
    def table_query():
        pool = Pool()
        Relation = pool.get('party.relation.all')
        RelationSynthesis = pool.get('party.synthesis.menu.relationship')
        party = pool.get('party.party').__table__()
        relation = Relation.__table__()
        query_table = party.join(relation, 'LEFT OUTER', condition=(
            party.id == relation.from_))
        return query_table.select(
            party.id,
            Max(relation.create_uid).as_('create_uid'),
            Max(relation.create_date).as_('create_date'),
            Max(relation.write_uid).as_('write_uid'),
            Max(relation.write_date).as_('write_date'),
            Literal(coog_string.translate_label(RelationSynthesis, 'name')).
            as_('name'), party.id.as_('party'),
            group_by=party.id)

    def get_icon(self, name=None):
        return 'party_relation'

    def get_rec_name(self, name):
        RelationSynthesis = Pool().get('party.synthesis.menu.relationship')
        return coog_string.translate_label(RelationSynthesis, 'name')


class SynthesisMenu(UnionMixin, model.CoogSQL, model.CoogView,
        model.ExpandTreeMixin):
    'Party Synthesis Menu'
    __name__ = 'party.synthesis.menu'

    name = fields.Char('Name')
    icon = fields.Function(fields.Char('Icon'), 'get_icon')
    party = fields.Many2One('party.party', 'Party', ondelete='SET NULL')
    sequence = fields.Integer('Sequence')
    parent = fields.Many2One('party.synthesis.menu', 'Parent',
        ondelete='CASCADE')
    childs = fields.One2Many('party.synthesis.menu', 'parent', 'Childs')

    @classmethod
    def __setup__(cls):
        super(SynthesisMenu, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @staticmethod
    def union_models():
        return [
            'party.synthesis.menu.action_close',
            'party.synthesis.menu.action_refresh',
            'party.party',
            'party.synthesis.menu.contact',
            'party.contact_mechanism',
            'party.synthesis.menu.address',
            'party.address',
            'party.synthesis.menu.party_interaction',
            'party.interaction',
            'party.synthesis.menu.relationship',
            'party.relation.all',
            ]

    @classmethod
    def union_field(cls, name, Model):
        union_field = super(SynthesisMenu, cls).union_field(name, Model)
        if Model.__name__ == 'party.party':
            if name == 'party':
                return Model._fields['id']
        elif Model.__name__ == 'party.synthesis.menu.address':
            if name == 'parent':
                return Model._fields['party']
        elif Model.__name__ == 'party.address':
            if name == 'parent':
                union_field = copy.deepcopy(Model._fields['party'])
                union_field.model_name = 'party.synthesis.menu.address'
                return union_field
            elif name == 'name':
                return Model._fields['street']
        elif Model.__name__ == 'party.synthesis.menu.contact':
            if name == 'parent':
                return Model._fields['party']
        elif Model.__name__ == 'party.contact_mechanism':
            if name == 'parent':
                union_field = copy.deepcopy(Model._fields['party'])
                union_field.model_name = 'party.synthesis.menu.contact'
                return union_field
            elif name == 'name':
                return Model._fields['value']
        elif Model.__name__ == 'party.synthesis.menu.party_interaction':
            if name == 'parent':
                return Model._fields['party']
        elif Model.__name__ == 'party.interaction':
            if name == 'parent':
                union_field = copy.deepcopy(Model._fields['party'])
                union_field.model_name = \
                    'party.synthesis.menu.party_interaction'
                return union_field
            elif name == 'name':
                return Model._fields['title']
        elif Model.__name__ == 'party.synthesis.menu.relationship':
            if name == 'parent':
                return Model._fields['party']
        elif Model.__name__ == 'party.relation.all':
            if name == 'parent':
                union_field = copy.deepcopy(Model._fields['from_'])
                union_field.model_name = \
                    'party.synthesis.menu.relationship'
                return union_field
            elif name == 'name':
                return Model._fields['type']
        elif (Model.__name__ == 'party.synthesis.menu.action_close' or
                Model.__name__ == 'party.synthesis.menu.action_refresh'):
            if name == 'party':
                return Model._fields['id']
        if name == 'party':
            return
        return union_field

    @classmethod
    def menu_order(cls, model):
        if model == 'party.synthesis.menu.address':
            return 2
        elif model == 'party.synthesis.menu.contact':
            return 1
        elif model == 'party.synthesis.menu.party_interaction':
            return 3
        elif model == 'party.synthesis.menu.relationship':
            return 4
        elif (model == 'party.synthesis.menu.action_close' or
                model == 'party.synthesis.menu.action_refresh'):
            return 0

    @classmethod
    def union_columns(cls, model):
        table, columns = super(SynthesisMenu, cls).union_columns(model)
        order = cls.menu_order(model)
        field = cls._fields['sequence']
        for idx, column in enumerate(columns):
            if getattr(column, 'output_name', None) == 'sequence':
                columns.pop(idx)
        columns.append(Cast(Literal(order or 0), field.sql_type().base).
            as_('sequence'))
        return table, columns

    @classmethod
    def search_global(cls, text):
        party_ids = Transaction().context.get('party_synthesis')
        if party_ids:
            for record in cls.search([
                        ('rec_name', 'ilike', '%%%s%%' % text),
                        ('party', 'in', party_ids),
                        ]):
                yield record.id, record.rec_name, None
        else:
            for i in super(SynthesisMenu, cls).search_global(text):
                yield i

    def get_icon(self, name):
        instance = self.union_unshard(self.id)
        if getattr(instance, 'get_icon', None) is not None:
            return instance.get_icon()

    def get_rec_name(self, name):
        instance = self.union_unshard(self.id)
        if getattr(instance, 'get_synthesis_rec_name', None) is not None:
            res = instance.get_synthesis_rec_name(name)
        elif getattr(instance, 'get_rec_name', None) is not None:
            res = instance.get_rec_name(name)
        else:
            res = self.name
        if self.childs and self.parent:
            res += ' (%s)' % len(self.childs)
        return res

    def _expand_tree(self, name):
        return not self.parent or self.parent and not self.parent.parent


class SynthesisMenuOpenState(model.CoogView):
    'Syntesis Menu Open State'
    __name__ = 'party.synthesis.menu.open_state'

    need_refresh = fields.Boolean('Need Refresh')


class SynthesisMenuOpen(Wizard):
    'Open Party Synthesis Menu'
    __name__ = 'party.synthesis.menu.open'

    start_state = 'check_reload'
    state = StateView('party.synthesis.menu.open_state', None, [])
    check_reload = StateTransition()
    open = StateAction('party_cog.act_menu_open')

    def transition_check_reload(self):
        pool = Pool()
        Menu = pool.get('party.synthesis.menu')
        User = pool.get('res.user')
        context = Transaction().context
        record = Menu.union_unshard(context['active_id'])
        if record.__name__ == 'party.synthesis.menu.action_close':
            user = Transaction().user
            user = User(user)
            user.party_synthesis = None
            user.party_synthesis_previous = None
            user.save()
            self.state.need_refresh = True
            return 'end'
        elif record.__name__ == 'party.synthesis.menu.action_refresh':
            self.state.need_refresh = True
            return 'end'
        else:
            self.state.need_refresh = False
            return 'open'

    def do_open(self, action):
        pool = Pool()
        Menu = pool.get('party.synthesis.menu')
        context = Transaction().context
        record = Menu.union_unshard(context['active_id'])
        action.update(self.get_action(record))
        parameters = self.get_action_parameters(record)
        return action, parameters

    def get_action(self, record):
        Model = record.__class__
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Action = pool.get('ir.action')
        actions = {
            'res_model': Model.__name__,
            'views': [(None, 'form'), (None, 'tree')],
            }
        if Model.__name__ == 'party.synthesis.menu.address':
            actions['res_model'] = 'party.address'
            actions['pyson_domain'] = PYSONEncoder().encode(
                [('party', '=', record.id)])
            actions['views'] = list(reversed(actions['views']))
        elif Model.__name__ == 'party.synthesis.menu.contact':
            actions['res_model'] = 'party.contact_mechanism'
            actions['pyson_domain'] = PYSONEncoder().encode(
                [('party', '=', record.id)])
            actions['views'] = list(reversed(actions['views']))
        elif Model.__name__ == 'party.synthesis.menu.party_interaction':
            actions['res_model'] = 'party.interaction'
            actions['pyson_domain'] = PYSONEncoder().encode(
                [('party', '=', record.id)])
            actions['views'] = list(reversed(actions['views']))
        elif Model.__name__ == 'party.synthesis.menu.relationship':
            actions['res_model'] = 'party.relation.all'
            actions['pyson_domain'] = PYSONEncoder().encode(
                [('from_', '=', record.id)])
            actions['views'] = list(reversed(actions['views']))
        elif Model.__name__ == 'party.relation.all':
            action_id = Action.get_action_id(
                ModelData.get_id('party_cog', 'start_synthesis_menu'))
            action = Action(action_id)
            actions = Action.get_action_values(action.type, [action.id])[0]
        else:
            actions['res_id'] = [record.id]
        return actions

    def get_action_parameters(self, record):
        Model = record.__class__
        if Model.__name__ != 'party.relation.all':
            return {}
        return {'ids': [record.to.id]}

    def end(self):
        if self.state.need_refresh:
            return 'reload menu'


class SynthesisMenuSet(Wizard):
    'Set Party Synthesis Menu'
    __name__ = 'party.synthesis.menu.set'

    start_state = 'set'
    set = StateTransition()
    open = StateAction('party_cog.act_menu_open')

    def transition_set(self):
        pool = Pool()
        User = pool.get('res.user')
        user = Transaction().user
        with Transaction().set_user(0):
            user = User(user)
            ids = set(Transaction().context['active_ids'])
            if user.party_synthesis_previous:
                ids.update(set(json.loads(user.party_synthesis_previous)))
            ids = sorted(ids)
            user.party_synthesis = json.dumps(ids)
            user.party_synthesis_previous = user.party_synthesis
            user.save()
        return 'open'

    def do_open(self, action):
        pool = Pool()
        action.update({
            'res_model': 'party.party',
            'views': [(pool.get('ir.ui.view').search([('xml_id', '=',
                    'party_cog.party_view_synthesis_form')])[0].id, 'form')],
            'res_id': Transaction().context['active_ids'][0],
            })
        return action, {}

    def end(self):
        return 'reload menu'


class PartyReplace:
    __metaclass__ = PoolMeta
    __name__ = 'party.replace'

    @classmethod
    def __setup__(cls):
        super(PartyReplace, cls).__setup__()
        cls._error_messages.update({
                'different_first_name': ("Parties have different first names: "
                    "%(source_name)s vs %(destination_name)s."),
                })

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('party.interaction', 'party'),
            ('party.relation', 'from_'),
            ('party.relation', 'to'),
            ]

    def check_similarity(self):
        super(PartyReplace, self).check_similarity()
        source = self.ask.source
        destination = self.ask.destination
        if source.first_name != destination.first_name:
            key = 'party.replace first_name %s %s' % (source.id, destination.id)
            self.raise_user_warning(key, 'different_first_name', {
                    'source_name': '%s %s' % (source.name, source.first_name),
                    'destination_name': '%s %s' % (destination.name,
                        destination.first_name),
                    })


class PartyReplaceAsk:
    __metaclass__ = PoolMeta
    __name__ = 'party.replace.ask'

    is_person = fields.Function(
        fields.Boolean('Person'), 'on_change_with_is_person')
    gender = fields.Function(
        fields.Char('Gender'), 'on_change_with_gender')
    birth_date = fields.Function(
        fields.Date('Birth Date'), 'on_change_with_birth_date')

    @classmethod
    def __setup__(cls):
        super(PartyReplaceAsk, cls).__setup__()
        cls.destination.domain += [
            ('is_person', '=', Eval('is_person')),
            ('gender', '=', Eval('gender')),
            ('birth_date', '=', Eval('birth_date')),
            ]
        cls.destination.depends += ['is_person', 'gender', 'birth_date']

    @fields.depends('source')
    def on_change_with_is_person(self, name=None):
        return self.source.is_person if self.source else None

    @fields.depends('source')
    def on_change_with_gender(self, name=None):
        return self.source.gender if self.source else None

    @fields.depends('source')
    def on_change_with_birth_date(self, name=None):
        return self.source.birth_date if self.source else None

    @fields.depends('destination')
    def on_change_source(self):
        super(PartyReplaceAsk, self).on_change_source()
        if not self.source and self.destination:
            self.destination = None


class PartyErase:
    __metaclass__ = PoolMeta
    __name__ = 'party.erase'

    def get_transform(self, fname):

        class Transform(Function):
            __slots__ = ()
            _function = fname

        return Transform

    def to_erase(self, party_id):
        to_erase = super(PartyErase, self).to_erase(party_id)
        pool = Pool()
        Party = pool.get('party.party')
        ContactHistory = pool.get('party.interaction')
        to_erase.extend([
                (Party, [('id', '=', party_id)], True,
                    ['first_name', 'ssn', 'birth_name', 'birth_date',
                    'extra_data'],
                    [None, None, None, None, None]),
                (ContactHistory, [('party', '=', party_id)], True,
                    ['address', 'comment', 'attachment', 'for_object_ref'],
                    [None, None, None, None])
                ])
        md5hash = self.get_transform('MD5')
        res = []
        for Model, domain, resource, columns, values in to_erase:
            updated_values = []
            for col, value in zip(columns, values):
                f = Model._fields.get(col)
                if f and f._type in ('char', 'text') and f.required \
                        and value is None:
                    value = md5hash
                updated_values.append(value)
            res.append((Model, domain, resource, columns, updated_values))
        return res

    def transition_erase(self):
        pool = Pool()
        Party = pool.get('party.party')
        parties = replacing = [self.ask.party]
        with Transaction().set_context(active_test=False):
            while replacing:
                replacing = Party.search([
                        ('replaced_by', 'in', map(int, replacing))])
                parties += replacing
        for party in parties:
            self.check_erase(party)
            party.is_anonymized = True
        Party.save(parties)
        return super(PartyErase, self).transition_erase()
