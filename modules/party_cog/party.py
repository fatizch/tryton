# -*- coding:utf-8 -*-
import copy
import StringIO

try:
    import simplejson as json
except ImportError:
    import json

from sql.aggregate import Max
from sql import Literal, Cast
from sql.operators import Concat
from sql.conditionals import Coalesce

from trytond.model import Unique
from trytond.pyson import Eval, Bool
from trytond.pool import PoolMeta, Pool
from trytond.tools import grouped_slice

from trytond.rpc import RPC
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateAction, StateTransition, StateView
from trytond.pyson import PYSONEncoder
from trytond.modules.cog_utils import utils, fields, model, export
from trytond.modules.cog_utils import coop_string, UnionMixin


__metaclass__ = PoolMeta
__all__ = [
    'Party',
    'PartyIdentifier',
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
    _func_key = 'code'

    is_person = fields.Boolean('Person')
    is_company = fields.Boolean('Company')

    identifiers = fields.One2Many('party.identifier', 'party', 'Identifiers')
    summary = fields.Function(fields.Text('Summary'), 'get_summary')
    main_address = fields.Function(
        fields.Many2One('party.address', 'Main Address'),
        'get_main_address_id', searcher='search_main_address')
    ####################################
    # Person information
    gender = fields.Selection(GENDER, 'Gender', states={
            'invisible': ~STATES_PERSON,
            'required': STATES_PERSON,
            }, depends=['is_person'])
    gender_string = gender.translated('gender')
    first_name = fields.Char('First Name', states={
            'invisible': ~STATES_PERSON,
            'required': STATES_PERSON,
            }, depends=['is_person'])
    birth_name = fields.Char('Birth Name', states={
            'invisible': ~STATES_PERSON
            }, depends=['is_person'])
    birth_date = fields.Date('Birth Date', states={
            'invisible': ~STATES_PERSON,
            'required': STATES_PERSON,
            }, depends=['is_person'])
    ssn = fields.EmptyNullChar('SSN', states={
            'invisible': ~STATES_PERSON,
            'required': Eval('ssn_required', False)
            }, depends=['is_person', 'ssn_required'])
    ssn_required = fields.Function(fields.Boolean('SSN Required'),
        'get_SSN_required')
    ####################################
    # Company information
    short_name = fields.Char('Short Name',
        states={'invisible': ~STATES_COMPANY},
        depends=['is_company'])
    parent = fields.Many2One('party.party', 'Parent',
        states={'invisible': ~STATES_COMPANY}, depends=['is_company'])
    children = fields.One2Many('party.party', 'parent', 'Children',
        states={'invisible': ~STATES_COMPANY}, depends=['is_company'])
    logo = fields.Binary('Logo', states={'invisible': ~STATES_COMPANY},
        depends=['is_company'])
    ####################################
    synthesis = fields.One2Many('party.synthesis.menu', 'party', 'Synthesis',
        readonly=True)
    synthesis_rec_name = fields.Function(
        fields.Char('Name'), 'get_synthesis_rec_name')
    last_modification = fields.Function(fields.DateTime('Last Modification'),
        'get_last_modification')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('SSN_uniq', Unique(t, t.ssn),
             'The SSN of the party must be unique.')
        ]
        cls._error_messages.update({
                'duplicate_party': ('Duplicate(s) already exist(s) : %s'),
                })
        cls.__rpc__.update({'ws_create_person': RPC(readonly=False)})
        cls._buttons.update({
                'button_start_synthesis_menu': {},
                })
        cls._order.insert(0, ('last_modification', 'DESC'))
        for contact_type in ('phone', 'mobile', 'fax', 'email', 'website'):
            contact_field = getattr(cls, contact_type)
            contact_field.setter = 'set_contact'
            contact_field.readonly = False
        cls.vat_number.states = {'invisible': True}
        cls.vat_country.states = {'invisible': True}
        cls.full_name.searcher = 'search_full_name'

    @classmethod
    def view_attributes(cls):
        return super(Party, cls).view_attributes() + [
            ('/form/group[@id="person"]', 'states',
                {'invisible': ~Eval('is_person')}),
            ('/form/group[@id="company"]', 'states',
                {'invisible': ~Eval('is_company')}),
            ('/form/notebook/page[@id="tree"]', 'states',
                {'invisible': ~Eval('is_company')}),
            ('/form/group[@id="name"]', 'states',
                {'invisible': Eval('is_company') | Eval('is_person')}),
            ]

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
    def domain_duplicate_for_person(cls, party):
        return [
            ('id', '!=', party.id),
            ('name', 'ilike', party.name),
            ('first_name', 'ilike', party.first_name),
            ('birth_date', '=', party.birth_date),
            ]

    @classmethod
    def domain_duplicate_for_company(cls, party):
        return [
            ('id', '!=', party.id),
            ('name', 'ilike', party.name),
            ('short_name', 'ilike', party.short_name),
            ]

    @classmethod
    def check_duplicates(cls, parties):
        cursor = Transaction().cursor
        in_max = cursor.IN_MAX
        for i in range(0, len(parties), in_max):
            sub_parties = [p for p in parties[i:i + in_max]]
            domain = ['OR']
            for party in sub_parties:
                if party.is_person:
                    domain.append(cls.domain_duplicate_for_person(party))
                else:
                    domain.append(cls.domain_duplicate_for_company(party))
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
                    messages.append('%s %s\n' % (party.name, party.short_name))
            if messages:
                cls.raise_user_warning('Duplicate Party', 'duplicate_party',
                    ','.join(messages))

    @classmethod
    def validate(cls, parties):
        super(Party, cls).validate(parties)
        cls.check_duplicates(parties)

    @classmethod
    def copy(cls, parties, default=None):
        default = default.copy() if default else {}
        default.setdefault('synthesis', None)
        default.setdefault('first_name', 'temp_for_copy')
        default.setdefault('name', 'temp_for_copy')
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
        return super(Party, cls)._export_skips() | {'code_length', 'synthesis'}

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
            return '[%s] %s' % (self.code, self.full_name)

    def get_synthesis_rec_name(self, name):
        if self.is_person:
            res = '%s %s %s' % (coop_string.translate_value(
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
        if self.is_company:
            return 'coopengo-company'
        return 'coopengo-party'

    @classmethod
    def search_global(cls, text):
        for record, rec_name, icon in super(Party, cls).search_global(text):
            yield record, rec_name, record.get_icon()

    def get_relation_with(self, target, at_date=None):
        if not at_date:
            at_date = utils.today()
        kind = [rel.type.code for rel in
            utils.get_good_versions_at_date(self, 'relations', at_date)
            if rel.to.id == target.id]
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
        res = {}
        for party in parties:
            res[party.id] = "<b>%s</b>\n" % party.get_rec_name(name)
            if party.is_person:
                res[party.id] = coop_string.get_field_as_summary(party, 'ssn')
                res[party.id] += coop_string.get_field_as_summary(
                    party, 'birth_date')
                res[party.id] += coop_string.get_field_as_summary(
                    party, 'birth_name')
            if party.is_company:
                pass
            # res[party.id] += coop_string.get_field_as_summary(
            #    party, 'extra_data', True, at_date, lang=lang)
            res[party.id] += coop_string.get_field_as_summary(
                party, 'addresses', True, at_date, lang=lang)
        return res

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('first_name',) + tuple(clause[1:]),
            ('name',) + tuple(clause[1:]),
            ('code',) + tuple(clause[1:]),
            ('identifiers.code',) + tuple(clause[1:]),
        ]

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
        if self.is_company:
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
        for address in addresses:
            if not type or getattr(address, type):
                return address
        if addresses:
            return addresses[0]

    def get_main_address_id(self, name=None, at_date=None):
        address = self.address_get(at_date=at_date)
        return address.id if address else None

    def get_last_modification(self, name):
        return (self.write_date if self.write_date else self.create_date
            ).replace(microsecond=0)

    @classmethod
    def get_identifier(cls, parties, names):
        cursor = Transaction().cursor
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
            for elem in cursor.dictfetchall():
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

    @classmethod
    def default_lang(cls):
        return utils.get_user_language().id

    @fields.depends('gender')
    def on_change_gender(self):
        if self.gender == 'female':
            return
        self.birth_name = ''

    @classmethod
    def get_var_names_for_full_extract(cls):
        res = super(Party, cls).get_var_names_for_full_extract()
        res.extend(['is_person', 'is_company', 'gender', 'first_name',
            'birth_name', 'birth_date', 'ssn', 'short_name', 'addresses',
            'contact_mechanisms',
            ('lang', 'light')])
        return res

    @classmethod
    def set_contact(cls, ids, name, value):
        pool = Pool()
        Contact = pool.get('party.contact_mechanism')
        contact_to_save = []
        for party in ids:
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
                    Contact.create([{
                                'type': name,
                                'value': value,
                                'party': party.id,
                                'active': True
                                }])
            Contact.save(contact_to_save)

    def get_publishing_values(self):
        result = super(Party, self).get_publishing_values()
        result['name'] = self.name
        result['first_name'] = self.first_name
        result['birth_date'] = self.birth_date
        result['gender'] = coop_string.translate_value(self, 'gender')
        try:
            result['main_address'] = self.addresses[0]
        except:
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
    @model.CoopView.button_action('party_cog.start_synthesis_menu')
    def button_start_synthesis_menu(cls, parties):
        pass


class PartyIdentifier(model.CoopSQL, model.CoopView):
    'Party Identifier'
    __name__ = 'party.identifier'
    _rec_name = 'code'

    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
        required=True, select=True)
    type = fields.Selection('get_types', 'Type')
    code = fields.Char('Code', required=True)

    @classmethod
    def get_types(cls):
        return [
            (None, ''),
            ]

    @classmethod
    def validate(cls, identifiers):
        super(PartyIdentifier, cls).validate(identifiers)
        for identifier in identifiers:
            identifier.check_code()

    def check_code(self):
        pass


class SynthesisMenuActionCloseSynthesis(model.CoopSQL):
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
            Literal(coop_string.translate_label(PartyActionClose,
                'name')).as_('name'), Literal(party_id).as_('party'))

    def get_icon(self, name=None):
        return 'coopengo-close'

    def get_rec_name(self, name):
        PartyActionClose = Pool().get('party.synthesis.menu.action_close')
        return coop_string.translate_label(PartyActionClose, 'name')


class SynthesisMenuActionRefreshSynthesis(model.CoopSQL):
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
            Literal(coop_string.translate_label(PartyActionRefresh,
                'name')).as_('name'), Literal(party_id).as_('party'))

    def get_icon(self, name=None):
        return 'tryton-refresh'

    def get_rec_name(self, name):
        PartyActionRefresh = Pool().get('party.synthesis.menu.action_refresh')
        return coop_string.translate_label(PartyActionRefresh, 'name')


class SynthesisMenuPartyInteraction(model.CoopSQL):
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
            Literal(coop_string.translate_label(PartyInteractionSynthesis,
                'name')).as_('name'),
            party_interaction.party,
            group_by=party_interaction.party)

    def get_rec_name(self, name):
        PartyInteraction = Pool().get('party.synthesis.menu.party_interaction')
        return coop_string.translate_label(PartyInteraction, 'name')


class SynthesisMenuAddress(model.CoopSQL):
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
            Literal(coop_string.translate_label(AddressSynthesis, 'name')).
            as_('name'), party.id.as_('party'),
            group_by=party.id)

    def get_icon(self, name=None):
        return 'coopengo-address'

    def get_rec_name(self, name):
        AddressSynthesis = Pool().get('party.synthesis.menu.address')
        return coop_string.translate_label(AddressSynthesis, 'name')


class SynthesisMenuContact(model.CoopSQL):
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
            Literal(coop_string.translate_label(ContactSynthesis, 'name')).
            as_('name'), party.id.as_('party'),
            group_by=party.id)

    def get_icon(self, name=None):
        return 'contact'

    def get_rec_name(self, name):
        ContactSynthesis = Pool().get('party.synthesis.menu.contact')
        return coop_string.translate_label(ContactSynthesis, 'name')


class SynthesisMenuRelationship(model.CoopSQL):
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
            Literal(coop_string.translate_label(RelationSynthesis, 'name')).
            as_('name'), party.id.as_('party'),
            group_by=party.id)

    def get_icon(self, name=None):
        return 'party_relation'

    def get_rec_name(self, name):
        RelationSynthesis = Pool().get('party.synthesis.menu.relationship')
        return coop_string.translate_label(RelationSynthesis, 'name')


class SynthesisMenu(UnionMixin, model.CoopSQL, model.CoopView,
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
    def view_header_get(cls, value, view_type='form'):
        pool = Pool()
        Party = pool.get('party.party')
        context = Transaction().context
        value = super(SynthesisMenu, cls).view_header_get(value,
            view_type=view_type)
        if context.get('party'):
            party = Party(context['party'])
            value = '%s - %s' % (party.rec_name, value)
        return value

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


class SynthesisMenuOpenState(model.CoopView):
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
