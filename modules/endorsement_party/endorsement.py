from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, model
from trytond.modules.endorsement import values_mixin, relation_mixin
from trytond.model import Workflow


__metaclass__ = PoolMeta
__all__ = [
    'Address',
    'Party',
    'EndorsementParty',
    'EndorsementPartyAddress',
    'Endorsement',
    ]


class Address(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'party.address'


class EndorsementPartyAddress(relation_mixin(
            'endorsement.party.address.field', 'address', 'party.address',
            'Addresses'),
        model.CoopSQL, model.CoopView):
    'Endorsement Address'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.party.address'

    party_endorsement = fields.Many2One(
        'endorsement.party', 'Party Endorsement',
        required=True, select=True, ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.party_endorsement.definition.id

    def get_rec_name(self, name):
        if self.address:
            return self.address.rec_name
        else:
            return self.raise_user_error('new_address',
                raise_exception=False)

    @classmethod
    def updated_struct(cls, address):
        return {}


class Party:
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._buttons.update({
                'start_endorsement': {},
                })

    @classmethod
    @model.CoopView.button_action('endorsement.act_start_endorsement')
    def start_endorsement(cls, parties):
        pass


class Endorsement:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement'

    party_endorsements = fields.One2Many('endorsement.party', 'endorsement',
        'Party Endorsement', size=1)
    parties = fields.Function(
        fields.Many2Many('party.party', '', '', 'Parties'),
        'get_parties', searcher='search_parties')

    def get_parties(self, name):
        return [x.party.id for x in self.party_endorsements]

    @classmethod
    def search_parties(cls, name, clause):
        return [('party_endorsements.party',) + tuple(clause[1:])]

    def all_endorsements(self):
        tmp_result = super(Endorsement, self).all_endorsements()
        result = tmp_result + self.party_endorsements
        return result

    def find_parts(self, endorsement_part):
        # Finds the effective endorsement depending on the provided
        # endorsement part
        if endorsement_part.kind in ('party'):
            return self.party_endorsements
        return super(Endorsement, self).find_parts(endorsement_part)

    @classmethod
    def group_per_model(cls, endorsements):
        result = super(Endorsement, cls).group_per_model(endorsements)
        result['endorsement.party'] = [
            party_endorsement for endorsement in endorsements
            for party_endorsement in endorsement.party_endorsements]
        return result

    @classmethod
    def apply_order(cls):
        result = super(Endorsement, cls).apply_order()
        result.insert(0, 'endorsement.party')
        return result

    @classmethod
    @model.CoopView.button
    @Workflow.transition('applied')
    def apply(cls, endorsements):
        super(Endorsement, cls).apply(endorsements)
        for endorsement in endorsements:
            contracts = []
            for p_endors in endorsement.party_endorsements:
                contracts.extend(p_endors.contracts_to_update)
            contracts = list(set(contracts))
            if endorsement.definition.generate_contract_endorsements:
                cls.endorse_contracts(
                    contracts,
                    endorsement.definition.definition_for_contracts,
                    origin=endorsement)


class EndorsementParty(values_mixin('endorsement.party.field'),
        model.CoopSQL, model.CoopView):
    'Endorsement Party'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.party'
    _func_key = 'func_key'

    party = fields.Many2One('party.party', 'Party', required=True,
        ondelete='CASCADE',
        states={'readonly': Eval('state') == 'applied'}, depends=['state'])
    endorsement = fields.Many2One('endorsement', 'Endorsement', required=True,
        ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')
    state = fields.Function(
        fields.Selection([
                ('draft', 'Draft'),
                ('applied', 'Applied'),
                ], 'State'),
        'get_state', searcher='search_state')
    state_string = state.translated('state')
    endorsement_summary = fields.Function(
        fields.Text('Endorsement Summary'),
        'get_endorsement_summary')
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key')
    addresses = fields.One2Many('endorsement.party.address',
        'party_endorsement', 'Addresses', states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state', 'party', 'definition'],
        context={'definition': Eval('definition')})

    @classmethod
    def __setup__(cls):
        super(EndorsementParty, cls).__setup__()
        cls._error_messages.update({
                'only_one_endorsement_in_progress': 'There may only be one '
                'endorsement in_progress at a given time per party',
                'msg_address_modifications':
                'Addresses Modifications',
                })

    def get_func_key(self, name):
        return getattr(self.party, self.party._func_key)

    @classmethod
    def add_func_key(cls, values):
        if 'party' in values and '_func_key' in values['party']:
            values['_func_key'] = values['party']['_func_key']
        else:
            values['_func_key'] = 0

    @property
    def base_instance(self):
        if not self.party:
            return None
        if not self.endorsement.rollback_date:
            return self.party
        with Transaction().set_context(
                _datetime=self.endorsement.rollback_date,
                _datetime_exclude=True):
            return Pool().get('party.party')(self.party.id)

    def get_endorsement_summary(self, name):
        result = ['definition_section', self.definition.name, []]
        party_summary = self.get_summary('party.party', self.base_instance)
        if party_summary:
            result[2] += ['party_change_section', party_summary]

        address_summary = [address.get_summary('party.address',
                address.address) for address in self.addresses]
        if address_summary:
            result[2].append(['address_change_section',
                '%s :' % self.raise_user_error('msg_address_modifications',
                    raise_exception=False), address_summary])
        return ['title_section', self.party.full_name, result]

    def get_definition(self, name):
        return self.endorsement.definition.id if self.endorsement else None

    def get_state(self, name):
        return self.endorsement.state if self.endorsement else 'draft'

    @classmethod
    def search_state(cls, name, clause):
        return [('endorsement.state',) + tuple(clause[1:])]

    @classmethod
    def _get_restore_history_order(cls):
        return ['party.party']

    def do_restore_history(self):
        pool = Pool()
        models_to_restore = self._get_restore_history_order()
        restore_dict = {x: [] for x in models_to_restore}
        restore_dict['party.party'] += [self.party, self.base_instance]
        self._prepare_restore_history(restore_dict,
            self.endorsement.rollback_date)

        for model_name in models_to_restore:
            if not restore_dict[model_name]:
                continue
            pool.get(model_name).restore_history_before(
                list(set([x.id for x in restore_dict[model_name]])),
                self.endorsement.rollback_date)

    @classmethod
    def _prepare_restore_history(cls, instances, at_date):
        pass

    @classmethod
    def draft(cls, party_endorsements):
        for party_endorsement in party_endorsements:
            latest_applied, = cls.search([
                    ('party', '=', party_endorsement.party.id),
                    ('state', 'not in', ['draft', 'canceled', 'declined']),
                    ], order=[('applied_on', 'DESC')], limit=1)
            if latest_applied != party_endorsement:
                cls.raise_user_error('not_latest_applied',
                    party_endorsement.rec_name)

            party_endorsement.do_restore_history()
            party_endorsement.set_applied_on(None)
            party_endorsement.state = 'draft'
            party_endorsement.save()

    @classmethod
    def check_in_progress_unicity(cls, party_endorsements):
        count = Pool().get('endorsement').search_count([
                ('parties', 'in', [x.party.id for x in party_endorsements]),
                ('state', '=', 'in_progress')])
        if count:
            cls.raise_user_error('only_one_endorsement_in_progress')

    @classmethod
    def apply(cls, party_endorsements):
        pool = Pool()
        Party = pool.get('party.party')
        for p_endorsement in party_endorsements:
            party = p_endorsement.party
            if p_endorsement.endorsement.rollback_date:
                p_endorsement.set_applied_on(
                    p_endorsement.endorsement.rollback_date)
            else:
                p_endorsement.set_applied_on(party.write_date
                    or party.create_date)
            values = p_endorsement.apply_values()
            Party.write([party], values)
            p_endorsement.save()

    @property
    def contracts_to_update(self):
        pool = Pool()
        Contract = pool.get('contract')
        return Contract.search([('status', '=', 'active'),
                ['OR',
                    ('subscriber', '=', self.party),
                    ('covered_elements.party', '=', self.party)]])

    def set_applied_on(self, at_datetime):
        self.applied_on = at_datetime

    def get_endorsed_record(self):
        return self.party

    @property
    def new_addresses(self):
        elems = set([x for x in self.party.addresses])
        for elem in getattr(self, 'addresses', []):
            if elem.action == 'add':
                elems.add(elem)
            elif elem.action == 'remove':
                elems.remove(elem.address)
            else:
                elems.remove(elem.address)
                elems.add(elem)
        return elems

    @property
    def updated_struct(self):
        pool = Pool()
        EndorsementAddress = pool.get('endorsement.party.address')
        addresses = {}
        for address in self.new_addresses:
            addresses[address] = EndorsementAddress.updated_struct(address)
        return {
            'addresses': addresses,
            }

    def apply_values(self):
        values = self.values.copy() if self.values else {}
        addresses = []
        for address in self.addresses:
            addresses.append(address.apply_values())
        if addresses:
            values['addresses'] = addresses
        return values
