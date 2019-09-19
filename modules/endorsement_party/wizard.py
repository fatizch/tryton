# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import OrderedDict

from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, If

from trytond.modules.coog_core import fields, model, coog_string, utils
from trytond.modules.endorsement.wizard import (EndorsementWizardStepMixin,
    add_endorsement_step)
from trytond.modules.party_relationship.party import PartyRelationAll
from trytond.modules.party_cog.relationship \
    import PartyRelationAll as PartyRelationAllCoog

__all__ = [
    'AddressDisplayer',
    'ChangePartyAddress',
    'ChangePartyBirthDate',
    'ChangePartySSN',
    'PartyNameDisplayer',
    'ChangePartyName',
    'StartEndorsement',
    'StartEndorsementSSN',
    'SelectEndorsement',
    'RelationDisplayer',
    'ChangePartyRelationship',
    'PartyErase',
    ]


class AddressDisplayer(model.CoogView):
    'Address Displayer'

    __name__ = 'endorsement.party.change_address_displayer'

    previous_address = fields.One2Many('party.address', None,
        'Current Address', size=1,
        states={'invisible': Bool(Eval('is_new'))}, readonly=True)
    new_address = fields.One2Many('party.address', None, 'New Address',
        size=1)
    name = fields.Char('Name')
    date = fields.Date('Date')
    party = fields.Many2One('party.party', 'Party', readonly=True)
    is_new = fields.Boolean('Is New')
    address_endorsement = fields.Many2One('endorsement.party.address',
        'Address Endorsement')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.previous_address.force_readonly_view = True

    @classmethod
    def default_is_new(cls):
        return True

    @classmethod
    def default_new_address(cls):
        Country = Pool().get('country.country')
        good_id = Transaction().context.get('good_party')
        effective_date = Transaction().context.get('effective_date')
        new_address = {'party': good_id, 'start_date': effective_date,
            'name': '', 'street': '', 'zip': '', 'city': '',
            'subdivision': None}
        country = Country._default_country()
        if country:
            address_lines = {x: '' for x in country.get_address_lines()}
            new_address['country'] = country.id
            new_address['has_address_lines'] = bool(address_lines)
            new_address['address_lines'] = address_lines
        return [new_address]

    @fields.depends('date', 'is_new', 'new_address', 'party')
    def on_change_new_address(self):
        if not self.new_address:
            return
        self.name = self.new_address[0].get_rec_name(None)
        if hasattr(self.new_address[0], 'start_date'):
            self.date = self.new_address[0].start_date
        self.party = self.new_address[0].party

    @classmethod
    def view_attributes(cls):
        return super(AddressDisplayer, cls).view_attributes() + [
            ("/form/group[@id='previous_address']", 'states',
                {'invisible': Eval('is_new')}),
            ]

    def set_party(self, party):
        if self.party is None and self.is_new:
            self.party = party
            self.new_address[0].party = party
            self.new_address = list(self.new_address)


class ChangePartyAddress(EndorsementWizardStepMixin):
    'Change Party Address'

    __name__ = 'endorsement.party.change_address'

    displayers = fields.One2Many('endorsement.party.change_address_displayer',
        None, 'Addresses',
        depends=['party_id'],
        context={'good_party': Eval('party_id'),
            'effective_date': Eval('effective_date')})
    party_id = fields.Integer('party_id')

    @classmethod
    def is_multi_instance(cls):
        return False

    @classmethod
    def state_view_name(cls):
        return 'endorsement_party.' \
            'party_change_address_view_form'

    @fields.depends('party_id', 'displayers')
    def on_change_displayers(self):
        for displayer in self.displayers:
            displayer.set_party(self.party_id)
        self.displayers = list(self.displayers)

    @classmethod
    def _address_fields_to_extract(cls):
        return ['name', 'street', 'address_lines', 'has_address_lines', 'zip',
            'city', 'start_date', 'end_date', 'party', 'country',
            'zip_and_city', 'subdivision', 'active']

    def _get_parties(self):
        return {x.party.id: x
            for x in self.wizard.endorsement.party_endorsements}

    def step_default(self, name):
        pool = Pool()
        Address = pool.get('party.address')
        Zip = pool.get('country.zip')

        def set_zip_and_city(values):
            if set(['city', 'country', 'zip']).issubset(set(
                        values.keys())):
                zip_and_cities = Zip.search(
                    [
                        ('city', '=', values['city']),
                        ('zip', '=', values['zip']),
                        ('country', '=', values['country'])],
                    limit=1)
                if zip_and_cities:
                    values['zip_and_city'] = zip_and_cities[0].id
                else:
                    values['zip_and_city'] = None

        defaults = super(ChangePartyAddress, self).step_default()
        parties = self._get_parties()
        defaults.update({'displayers': []})
        for party_id, party_endorsement in parties.items():
            updated_struct = party_endorsement.updated_struct
            addresses = updated_struct['addresses']
            for address in addresses:
                displayer = {'party': party_id}
                if not address.__name__ == 'endorsement.party.address':
                    displayer.update({
                        'previous_address': [address.id],
                        'new_address': [address.id],
                        'name': Address(address.id).rec_name,
                        'date': Address(address.id).start_date,
                        'is_new': False,
                    })
                elif address.action == 'update':
                    values = model.dictionarize(address.address,
                        self._address_fields_to_extract())
                    values.update(address.values)
                    if address.address.zip_and_city:
                        set_zip_and_city(values)
                    displayer.update({
                            'address_endorsement': address.id,
                            'previous_address': [address.address.id],
                            'new_address': [values],
                            'name': Address(address.address.id).rec_name,
                            'date': Address(address.address.id).start_date,
                            'is_new': False,
                    })
                else:
                    values = address.values
                    if set(['city', 'country', 'zip']).issubset(set(
                                values.keys())):
                        set_zip_and_city(values)
                    displayer.update({
                            'address_endorsement': address.id,
                            'previous_address': None,
                            'new_address': [values],
                            'date': values.get('start_date', None),
                            'is_new': True,
                    })

                defaults['displayers'].append(displayer)
                defaults['party_id'] = \
                    self.wizard.endorsement.party_endorsements[0].party.id
        return defaults

    def step_update(self):
        pool = Pool()
        EndorsementAddress = pool.get('endorsement.party.address')
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        parties = self._get_parties()

        def get_save_values(address, prev_address):
            new_values = None
            if hasattr(address, '_save_values'):
                # We only use the save values that are not null,
                # except if the field was set for the previous address,
                # which means that the user wants to delete the field.
                # This is needed because a None field is a void string
                # in _save_values
                new_values = {k: v for k, v in
                    address._save_values.items() if k in
                    self._address_fields_to_extract() and
                    (v or getattr(prev_address, k, False))}
                new_values.pop('zip_and_city', None)
            return new_values

        for party_id, party_endorsement in parties.items():
            party = Party(party_id)
            addresses_added = None
            if party_endorsement.addresses:
                addresses_added = [x for x in party_endorsement.addresses if
                        x.action == 'add']
            for displayer in self.displayers:
                address = displayer.new_address[0]
                prev_address = displayer.previous_address[0] if \
                    displayer.previous_address else None
                new_values = get_save_values(address, prev_address)
                if new_values and 'address_lines' in new_values:
                    if prev_address:
                        utils.apply_dict(prev_address, new_values)
                        prev_address.check_country_values()
                    else:
                        fake_address = Address()
                        utils.apply_dict(fake_address, new_values)
                        fake_address.check_country_values()
                if not new_values:
                    continue
                elif not displayer.address_endorsement:
                    if not displayer.is_new:
                        new_values.pop('party', None)
                        if not displayer.address_endorsement:
                            address_endorsement = EndorsementAddress(
                                action='update',
                                party_endorsement=party_endorsement,
                                address=address,
                                relation=address.id,
                                definition=self.endorsement_definition,
                                values=new_values,
                                )
                        else:
                            address_endorsement = displayer.address_endorsement
                            address_endorsement.values = new_values
                    else:
                        if addresses_added:
                            raise ValidationError(gettext(
                                    'endorsement_party.msg_only_add_one'))
                        new_values = model.dictionarize(address,
                            self._address_fields_to_extract())
                        new_values.pop('zip_and_city')
                        if not displayer.address_endorsement:
                            address_endorsement = EndorsementAddress(
                                action='add',
                                party_endorsement=party_endorsement,
                                definition=self.endorsement_definition,
                                values={k: v for k, v in new_values.items()
                                    if v},
                                )
                        else:
                            address_endorsement = displayer.address_endorsement
                            address_endorsement.values = new_values
                else:  # update address endorsement
                    address_endorsement = displayer.address_endorsement
                    address_endorsement.values = new_values
                address_endorsement.save()

            if addresses_added and (
                    len(party.addresses) == len(self.displayers)
                    and not [x for x in self.displayers
                        if x.address_endorsement and
                        x.address_endorsement.action == 'add']):
                EndorsementAddress.delete(addresses_added)
            party_endorsement.save()


class ChangePartyBirthDate(EndorsementWizardStepMixin):
    'Change Party Birth Date'

    __name__ = 'endorsement.party.change_birth_date'

    current_birth_date = fields.Date('Current Birth Date', readonly=True)
    new_birth_date = fields.Date('New Birth Date')

    @classmethod
    def is_multi_instance(cls):
        return False

    @classmethod
    def state_view_name(cls):
        return 'endorsement_party.party_change_birth_date_view_form'

    @classmethod
    def _party_fields_to_extract(cls):
        return {}

    def _get_parties(self):
        return {x.party.id: x
            for x in self.wizard.endorsement.party_endorsements}

    def step_default(self, name):
        pool = Pool()
        Party = pool.get('party.party')
        defaults = super(ChangePartyBirthDate, self).step_default()
        parties = self._get_parties()
        party = Party(list(parties.keys())[0])
        party_endorsement = list(parties.values())[0]
        values = party_endorsement.values
        if 'birth_date' in values:
            defaults['new_birth_date'] = values['birth_date']
        else:
            defaults['new_birth_date'] = party.birth_date
        defaults['current_birth_date'] = party.birth_date
        return defaults

    def step_update(self):
        parties = self._get_parties()
        party_endorsement = list(parties.values())[0]
        party_endorsement.values = {'birth_date': self.new_birth_date}
        party_endorsement.save()


class ChangePartySSN(EndorsementWizardStepMixin):
    'Change Party SSN'

    __name__ = 'endorsement.party.change_ssn'

    current_ssn = fields.Char('Current SSN', readonly=True)
    new_ssn = fields.Char('New SSN')

    @classmethod
    def is_multi_instance(cls):
        return False

    @classmethod
    def state_view_name(cls):
        return 'endorsement_party.' \
            'party_change_ssn_view_form'

    @classmethod
    def _party_fields_to_extract(cls):
        return {}

    def _get_parties(self):
        return {x.party.id: x
            for x in self.wizard.endorsement.party_endorsements}

    def step_default(self, name):
        pool = Pool()
        Party = pool.get('party.party')
        defaults = super(ChangePartySSN, self).step_default()
        parties = self._get_parties()
        party = Party(list(parties.keys())[0])
        party_endorsement = list(parties.values())[0]
        values = party_endorsement.values
        if 'ssn' in values:
            defaults['new_ssn'] = values['ssn']
        else:
            defaults['new_ssn'] = party.ssn
        defaults['current_ssn'] = party.ssn
        return defaults

    def step_update(self):
        pool = Pool()
        Party = pool.get('party.party')
        test_party = Party(ssn=self.new_ssn)
        test_party.check_ssn()
        parties = self._get_parties()
        party_endorsement = list(parties.values())[0]
        party_endorsement.values = {'ssn': self.new_ssn}
        party_endorsement.save()


class PartyNameDisplayer(model.CoogView):
    'Change Party Name Displayer'

    __name__ = 'endorsement.party.change_name.displayer'

    party_rec_name = fields.Char('Party', readonly=True)
    current_name = fields.Char('Current Name', readonly=True)
    current_first_name = fields.Char('Current First Name', readonly=True)
    current_birth_name = fields.Char('Current Birth Name', readonly=True)
    current_email = fields.Char('Current Email', readonly=True)
    current_gender = fields.Selection('get_possible_genders', 'Current Gender',
        readonly=True)
    name = fields.Char('New Name')
    first_name = fields.Char('New First Name')
    birth_name = fields.Char('New Birth Name')
    email = fields.Char('New Email')
    gender = fields.Selection('get_possible_genders', 'New Gender')

    @classmethod
    def get_possible_genders(cls):
        Party = Pool().get('party.party')
        return [
            (x, coog_string.translate(Party, 'gender', y, ttype='selection'))
            for x, y in Party._fields['gender'].selection]


class ChangePartyName(EndorsementWizardStepMixin):
    'Change Party Name'

    __name__ = 'endorsement.party.change_name'

    parties = fields.One2Many(
        'endorsement.party.change_name.displayer', None, 'Parties')

    @classmethod
    def view_attributes(cls):
        return super(ChangePartyName, cls).view_attributes() + [
            ('/form/group[@id="invisible"]', 'states',
                {'invisible': True}),
            ]

    @classmethod
    def state_view_name(cls):
        return 'endorsement_party.' \
            'party_change_name_view_form'

    @classmethod
    def _party_fields_to_extract(cls):
        return {'birth_name', 'email', 'first_name', 'gender', 'name'}

    def _get_parties(self):
        res = OrderedDict()
        for party_endorsement in self.wizard.endorsement.party_endorsements:
            res[party_endorsement.party.id] = party_endorsement
        return res

    def step_default(self, name):
        pool = Pool()
        Party = pool.get('party.party')
        displayers = []
        defaults = super(ChangePartyName, self).step_default()
        for party, party_endorsement in zip(Party.browse(
                    self._get_parties().keys()), self._get_parties().values()):
            displayer = {'party_rec_name': party.rec_name}
            values = party_endorsement.values
            for fname in self._party_fields_to_extract():
                displayer[fname] = values.get(fname, getattr(party, fname))
                displayer['current_' + fname] = getattr(party, fname)
            displayers.append(displayer)
        defaults['parties'] = displayers
        return defaults

    def step_update(self):
        pool = Pool()
        Party = pool.get('party.party')
        for party, party_endorsement, displayer in zip(
                Party.browse(list(self._get_parties().keys())),
                list(self._get_parties().values()), self.parties):
            new_values = {}
            for fname in self._party_fields_to_extract():
                if getattr(displayer, fname) != getattr(
                        displayer, 'current_' + fname):
                    new_values[fname] = getattr(displayer, fname)
            party_endorsement.values = new_values
            party_endorsement.save()


class RelationDisplayer(PartyRelationAll, PartyRelationAllCoog):
    'Relation Displayer'

    __name__ = 'endorsement.party.change_relation_displayer'

    previous_relation = fields.One2Many('party.relation.all', None,
        'Current Relation', size=1,
        states={'invisible': Bool(Eval('is_new'))}, readonly=True)
    is_new = fields.Boolean('Is New')
    relation_endorsement = fields.Many2One('endorsement.party.relation',
        'Relation Endorsement')
    to_remove = fields.Boolean('Remove', states={
            'readonly': Bool(Eval('is_new', False))}, depends=['is_new'])

    @classmethod
    def default_is_new(cls):
        return True

    @classmethod
    def default_from_(cls):
        return Transaction().context.get('good_party')


class ChangePartyRelationship(EndorsementWizardStepMixin):
    'Change Party Relationship'

    __name__ = 'endorsement.party.change_relations'

    displayers = fields.One2Many('endorsement.party.change_relation_displayer',
        None, 'Relations',
        depends=['party_id'],
        context={'good_party': Eval('party_id'),
            'effective_date': Eval('effective_date')})
    party_id = fields.Integer('party_id')

    @classmethod
    def state_view_name(cls):
        return 'endorsement_party.party_change_relations_view_form'

    @classmethod
    def _relation_fields_to_extract(cls):
        return ['from_', 'to', 'type', 'start_date', 'end_date']

    def _get_parties(self):
        res = OrderedDict()
        for party_endorsement in self.wizard.endorsement.party_endorsements:
            res[party_endorsement.party.id] = party_endorsement
        return res

    def step_default(self, name):
        defaults = super(ChangePartyRelationship, self).step_default()
        parties = self._get_parties()
        defaults.update({'displayers': []})
        for party_id, party_endorsement in parties.items():
            updated_struct = party_endorsement.updated_struct
            relations = updated_struct['relations']
            for relation in relations:
                if not relation.__name__ == 'endorsement.party.relation':
                    values = model.dictionarize(relation,
                        self._relation_fields_to_extract())
                    displayer = values
                    displayer.update({
                            'previous_relation': [relation.id],
                            'is_new': False,
                            'relation_endorsement': None,
                            })
                elif relation.action == 'update':
                    values = model.dictionarize(relation.relationship,
                        self._relation_fields_to_extract())
                    displayer = values
                    displayer.update(relation.values)
                    displayer.update({
                            'relation_endorsement': relation.id,
                            'previous_relation': [relation.relationship.id],
                            'is_new': False,
                            })
                else:
                    displayer = relation.values
                    displayer.update({
                            'relation_endorsement': relation.id,
                            'previous_relation': None,
                            'is_new': True,
                            })

                defaults['displayers'].append(displayer)
                defaults['party_id'] =\
                    self.wizard.endorsement.party_endorsements[0].party.id
        return defaults

    def step_update(self):
        pool = Pool()
        EndorsementRelation = pool.get('endorsement.party.relation')
        Party = pool.get('party.party')
        parties = self._get_parties()

        def get_save_values(relation, prev_relation):
            res = {}
            if not hasattr(relation, '_save_values'):
                return
            for field in self._relation_fields_to_extract():
                relation_save_values = relation._save_values
                if (hasattr(prev_relation, field) and
                        field in relation_save_values and
                        getattr(relation, field, False) !=
                        getattr(prev_relation, field, False) or
                        not prev_relation and field in relation_save_values):
                    res[field] = relation_save_values[field]
            return res

        for party_id, party_endorsement in parties.items():
            party = Party(party_id)
            relations_added = None
            if party_endorsement.relations:
                relations_added = [x for x in party_endorsement.relations if
                        x.action == 'add']
            for displayer in self.displayers:
                prev_relation = displayer.previous_relation[0] if\
                    (getattr(displayer, 'previous_relation', None) and
                        displayer.previous_relation) else None
                if displayer.to_remove and prev_relation:
                    relation_endorsement = EndorsementRelation(
                        action='remove',
                        party_endorsement=party_endorsement,
                        relationship=prev_relation,
                        relation=prev_relation.id,
                        definition=self.endorsement_definition
                        )
                    relation_endorsement.save()
                    continue

                new_values = get_save_values(displayer, prev_relation)
                if not new_values:
                    continue
                elif not displayer.relation_endorsement:
                    if not displayer.is_new:
                        if not displayer.relation_endorsement:
                            relation_endorsement = EndorsementRelation(
                                action='update',
                                party_endorsement=party_endorsement,
                                relationship=prev_relation,
                                relation=prev_relation.id,
                                definition=self.endorsement_definition,
                                values=new_values,
                                )
                        else:
                            relation_endorsement = \
                                displayer.relation_endorsement
                            relation_endorsement.values = new_values
                    else:
                        if relations_added:
                            raise ValidationError(gettext(
                                    'endorsement_party.msg_only_add_one'))
                        new_values = model.dictionarize(displayer,
                            self._relation_fields_to_extract())
                        if not displayer.relation_endorsement:
                            relation_endorsement = EndorsementRelation(
                                action='add',
                                party_endorsement=party_endorsement,
                                definition=self.endorsement_definition,
                                values={k: v for k, v in new_values.items()
                                    if v},
                                )
                        else:
                            relation_endorsement = \
                                displayer.relation_endorsement
                            relation_endorsement.values = new_values
                else:
                    relation_endorsement = displayer.relation_endorsement
                    relation_endorsement.values = new_values
                relation_endorsement.save()

            if relations_added and (
                    len(party.relations) == len(self.displayers)
                    and not [x for x in self.displayers
                        if x.relation_endorsement and
                        x.relation_endorsement.action == 'add']):
                EndorsementRelation.delete(relations_added)
            party_endorsement.save()


class SelectEndorsement(model.CoogView):
    'Select Endorsement'

    __name__ = 'endorsement.start.select_endorsement'

    party = fields.Many2One('party.party', 'Party', domain=[
            If(Bool(Eval('possible_parties', False)),
                [('id', 'in', Eval('possible_parties'))],
                [])], depends=['possible_parties'])
    possible_parties = fields.Many2Many('party.party', None, None, 'Parties')

    @classmethod
    def __setup__(cls):
        super(SelectEndorsement, cls).__setup__()
        cls.endorsement_definition.domain = ['AND',
            cls.endorsement_definition.domain,
            If(~Eval('party', False),
                [('ordered_endorsement_parts.endorsement_part.kind', '!=',
                        'party')],
                If(~Eval('contract', False),
                    [('ordered_endorsement_parts.endorsement_part.kind', '=',
                            'party')],
                    []))]
        cls.endorsement_definition.depends += ['contract', 'party']
        cls.contract.domain = [
            If(Bool(Eval('party', False)),
                [('parties', '=', Eval('party'))],
                [])]
        cls.contract.depends += ['party']
        cls.contract.states['invisible'] = ~Bool(Eval('contract', False))

    @fields.depends('party', 'possible_parties')
    def on_change_contract(self):
        super(SelectEndorsement, self).on_change_contract()
        self.possible_parties = self.contract.parties if self.contract else []
        if not self.party:
            self.party = utils.auto_complete_with_domain(self, 'party')

    @fields.depends('applicant', 'party', 'contract')
    def on_change_party(self):
        if self.party:
            self.applicant = self.party
        if not self.contract:
            self.contract = utils.auto_complete_with_domain(self, 'contract')

    @fields.depends('party', 'possible_parties')
    def on_change_effective_date(self):
        super(SelectEndorsement, self).on_change_effective_date()

    def _get_new_endorsement(self):
        endorsement = super(SelectEndorsement, self)._get_new_endorsement()
        if (getattr(self, 'party', None) and
                any([p.endorsement_part.kind == 'party' for p in
                self.endorsement_definition.ordered_endorsement_parts])):
            endorsement.party_endorsements = [{
                    'party': self.party.id,
                    'values': {},
                    }]
        return endorsement


class StartEndorsement(metaclass=PoolMeta):
    __name__ = 'endorsement.start'

    def transition_start(self):
        if Transaction().context.get('active_model') != 'endorsement':
            return 'select_endorsement'
        else:
            return super(StartEndorsement, self).transition_start()

    def default_select_endorsement(self, name):
        defaults = super(StartEndorsement, self).default_select_endorsement(
            name)
        if Transaction().context.get('active_model') == 'party.party':
            defaults['party'] = Transaction().context.get('active_id')
        return defaults


add_endorsement_step(StartEndorsement, ChangePartyBirthDate,
    'change_party_birth_date')

add_endorsement_step(StartEndorsement, ChangePartyAddress,
    'change_party_address')

add_endorsement_step(StartEndorsement, ChangePartyName,
    'change_party_name')

add_endorsement_step(StartEndorsement, ChangePartyRelationship,
    'change_party_relationship')


class StartEndorsementSSN(metaclass=PoolMeta):
    __name__ = 'endorsement.start'


add_endorsement_step(StartEndorsementSSN, ChangePartySSN,
    'change_party_ssn')


class PartyErase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def transition_erase(self):
        pool = Pool()
        Party = pool.get('party.party')
        parties = replacing = [self.ask.party]
        with Transaction().set_context(active_test=False):
            while replacing:
                replacing = Party.search([
                        ('replaced_by', 'in', list(map(int, replacing)))
                        ])
                parties += replacing
        for party in parties:
            self.check_erase(party)
            self.erase_endorsement_values(party.id)
        return super(PartyErase, self).transition_erase()

    def erase_endorsement_values(self, party_id):
        pool = Pool()
        EndorsementParty = pool.get('endorsement.party')
        endorsements_to_erase = EndorsementParty.search([
                ('party', '=', party_id)])
        keys_to_erase = ['name', 'first_name', 'ssn', 'birth_name',
            'birth_date']
        for endorsement in endorsements_to_erase:
            values = endorsement.values
            erased_values = endorsement.values
            for key in keys_to_erase:
                if values.get(key, None):
                    erased_values[key] = None
            endorsement.values = erased_values
        EndorsementParty.save(endorsements_to_erase)
