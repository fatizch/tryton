from collections import OrderedDict

from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import fields, model
from trytond.modules.endorsement import (EndorsementWizardStepMixin,
    add_endorsement_step)

__metaclass__ = PoolMeta
__all__ = [
    'AddressDisplayer',
    'ChangePartyAddress',
    'ChangePartyBirthDate',
    'ChangePartySSN',
    'PartyNameDisplayer',
    'ChangePartyName',
    'StartEndorsement',
    'SelectEndorsement',
    ]


class AddressDisplayer(model.CoopView):
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
    def default_is_new(cls):
        return True

    @classmethod
    def default_new_address(cls):
        good_id = Transaction().context.get('good_party')
        effective_date = Transaction().context.get('effective_date')
        return [{'party': good_id, 'start_date': effective_date}]

    @fields.depends('new_address', 'is_new')
    def on_change_new_address(self):
        self.name = self.new_address[0].get_rec_name(None)
        if hasattr(self.new_address[0], 'start_date'):
            self.date = self.new_address[0].start_date
        self.party = self.new_address[0].party


class ChangePartyAddress(EndorsementWizardStepMixin, model.CoopView):
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
    def __setup__(cls):
        super(ChangePartyAddress, cls).__setup__()
        cls._error_messages.update({
                'only_add_one': 'Only one new address can be added',
                })

    @classmethod
    def state_view_name(cls):
        return 'endorsement_party.' \
            'party_change_address_view_form'

    @classmethod
    def _address_fields_to_extract(cls):
        return ['name', 'street', 'streetbis', 'zip', 'city', 'start_date',
            'end_date', 'party', 'country', 'zip_and_city', 'subdivision']

    def _get_parties(self):
        return {x.party.id: x
            for x in self.wizard.endorsement.party_endorsements}

    def step_default(self, name):
        pool = Pool()
        Address = pool.get('party.address')
        Zip = pool.get('country.zipcode')

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
        for party_id, party_endorsement in parties.iteritems():
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
                defaults['party_id'] =\
                    self.wizard.endorsement.party_endorsements[0].party.id
        return defaults

    def step_update(self):
        pool = Pool()
        EndorsementAddress = pool.get('endorsement.party.address')
        Party = pool.get('party.party')
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
                    address._save_values.iteritems() if k in
                    self._address_fields_to_extract() and
                    v or getattr(prev_address, k, False)}
                new_values.pop('zip_and_city', None)
            return new_values

        for party_id, party_endorsement in parties.iteritems():
            party = Party(party_id)
            addresses_added = None
            if party_endorsement.addresses:
                addresses_added = [x for x in party_endorsement.addresses if
                        x.action == 'add']
            for displayer in self.displayers:
                address = displayer.new_address[0]
                prev_address = displayer.previous_address[0] if\
                    displayer.previous_address else None
                new_values = get_save_values(address, prev_address)
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
                            self.raise_user_error('only_add_one')
                        new_values = model.dictionarize(address,
                            self._address_fields_to_extract())
                        new_values.pop('zip_and_city')
                        if not displayer.address_endorsement:
                            address_endorsement = EndorsementAddress(
                                action='add',
                                party_endorsement=party_endorsement,
                                definition=self.endorsement_definition,
                                values={k: v for k, v in new_values.iteritems()
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


class ChangePartyBirthDate(EndorsementWizardStepMixin, model.CoopView):
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
        party = Party(parties.keys()[0])
        party_endorsement = parties.values()[0]
        values = party_endorsement.values
        if 'birth_date' in values:
            defaults['new_birth_date'] = values['birth_date']
        else:
            defaults['new_birth_date'] = party.birth_date
        defaults['current_birth_date'] = party.birth_date
        return defaults

    def step_update(self):
        parties = self._get_parties()
        party_endorsement = parties.values()[0]
        party_endorsement.values = {'birth_date': self.new_birth_date}
        party_endorsement.save()


class ChangePartySSN(EndorsementWizardStepMixin, model.CoopView):
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
        party = Party(parties.keys()[0])
        party_endorsement = parties.values()[0]
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
        party_endorsement = parties.values()[0]
        party_endorsement.values = {'ssn': self.new_ssn}
        party_endorsement.save()


class PartyNameDisplayer(model.CoopView):
    'Change Party Name Displayer'

    __name__ = 'endorsement.party.change_name.displayer'

    current_name = fields.Char('Current Name', readonly=True)
    current_first_name = fields.Char('Current First Name', readonly=True)
    current_birth_name = fields.Char('Current Birth Name', readonly=True)
    new_name = fields.Char('New Name')
    new_first_name = fields.Char('New First Name')
    new_birth_name = fields.Char('New Birth Name')


class ChangePartyName(EndorsementWizardStepMixin, model.CoopView):
    'Change Party Name'

    __name__ = 'endorsement.party.change_name'

    parties = fields.One2Many(
        'endorsement.party.change_name.displayer', None, 'Parties')

    @classmethod
    def state_view_name(cls):
        return 'endorsement_party.' \
            'party_change_name_view_form'

    @classmethod
    def _party_fields_to_extract(cls):
        return {}

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
            displayer = {}
            values = party_endorsement.values
            displayer['new_name'] = values.get('name', party.name)
            displayer['new_first_name'] = values.get('first_name',
                party.first_name)
            displayer['new_birth_name'] = values.get('birth_name',
                party.birth_name)
            displayer['current_name'] = party.name
            displayer['current_first_name'] = party.first_name
            displayer['current_birth_name'] = party.birth_name
            displayers.append(displayer)
        defaults['parties'] = displayers
        return defaults

    def step_update(self):
        pool = Pool()
        Party = pool.get('party.party')
        for party, party_endorsement, displayer in zip(
                Party.browse(self._get_parties().keys()),
                self._get_parties().values(), self.parties):
            new_values = {}
            if displayer.new_name or party.name:
                new_values.update({'name': displayer.new_name})
            if displayer.new_birth_name or party.birth_name:
                new_values.update({'birth_name': displayer.new_birth_name})
            if displayer.new_first_name or party.first_name:
                new_values.update({'first_name': displayer.new_first_name})
            party_endorsement.values = new_values
            party_endorsement.save()


class SelectEndorsement(model.CoopView):
    'Select Endorsement'

    __name__ = 'endorsement.start.select_endorsement'

    party = fields.Many2One('party.party', 'Party')


class StartEndorsement:
    __name__ = 'endorsement.start'

    def transition_start(self):
        if Transaction().context.get('active_model') != 'endorsement':
            return 'select_endorsement'
        else:
            return super(StartEndorsement, self).transition_start()

    def transition_start_endorsement(self):
        view = super(StartEndorsement, self).transition_start_endorsement()
        if hasattr(self.select_endorsement, 'party') and\
                self.select_endorsement.party:
            self.endorsement.party_endorsements = [{
                    'party': self.select_endorsement.party.id,
                    'values': {},
                    }]
        self.select_endorsement.endorsement.save()
        return view

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

add_endorsement_step(StartEndorsement, ChangePartySSN,
    'change_party_ssn')

add_endorsement_step(StartEndorsement, ChangePartyName,
    'change_party_name')
