# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.wizard import StateTransition, StateView, Button
from trytond.transaction import Transaction
from trytond.model import Workflow, Unique
from trytond.pyson import Eval, Bool, Equal

from trytond.modules.cog_utils import model, fields

__metaclass__ = PoolMeta
__all__ = [
    'Configuration',
    'EndorsementSet',
    'Endorsement',
    'EndorsementSetDecline',
    'EndorsementSetSelectDeclineReason',
    ]


class Configuration:
    __name__ = 'endorsement.configuration'

    endorsement_set_number_sequence = fields.Property(
        fields.Many2One('ir.sequence', 'Endorsement Set Number Sequence'))


class EndorsementSet(model.CoopSQL, model.CoopView):
    'Endorsement Set'

    __name__ = 'endorsement.set'
    _rec_name = 'number'

    number = fields.Char('Number', readonly=True)
    endorsements = fields.One2Many('endorsement', 'endorsement_set',
        'Endorsements', target_not_required=True)
    contract_set = fields.Function(
        fields.Many2One('contract.set', 'Contract Set'),
        'get_contract_set', searcher='search_contract_set')
    contracts_summary = fields.Function(
        fields.Text('Contracts Summary'), 'get_contracts_summary')
    subscribers_summary = fields.Function(
        fields.Text('Subcribers Summary'), 'get_subscribers_summary')
    contracts_endorsements_summary = fields.Function(
        fields.Text('Endorsements Summary'),
        'get_contracts_endorsements_summary')
    effective_date = fields.Function(
        fields.Date('Effective Date'),
        'get_effective_date', setter='set_effective_date')
    state = fields.Function(
        fields.Selection([
                ('draft', 'Draft'),
                ('in_progress', 'In Progress'),
                ('applied', 'Applied'),
                ('canceled', 'Canceled'),
                ('declined', 'Declined'),
                ], 'State'), 'get_state')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')
    contracts = fields.Function(
        fields.One2Many('contract', None, 'Contracts'),
        'get_contracts')
    endorsements_summary = fields.Function(
        fields.Text('Endorsements Summary'),
        'get_endorsements_summary')

    @classmethod
    def __setup__(cls):
        super(EndorsementSet, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('number_uniq', Unique(t, t.number),
                'The endorsement set number must be unique.')
        ]
        cls._buttons.update({
                'button_decline_set': {
                    "invisible": Bool(Equal(Eval('state'), 'declined'))},
                'reset': {
                    "invisible": ~Eval('state').in_(['draft'])},
                })
        cls._error_messages.update({
            'effective_date_already_set': 'The effective date is already set.',
            'no_sequence_defined': 'No sequence defined in configuration',
            })

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Configuration = pool.get('endorsement.configuration')

        config = Configuration(1)
        if not config.endorsement_set_number_sequence:
            cls.raise_user_error('no_sequence_defined')
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            if not values.get('number'):
                values['number'] = Sequence.get_id(
                    config.endorsement_set_number_sequence.id)
        return super(EndorsementSet, cls).create(vlist)

    @classmethod
    @model.CoopView.button_action('endorsement_set.act_decline_set')
    def button_decline_set(cls, endorsements):
        pass

    @classmethod
    @model.CoopView.button
    def reset(cls, endorsement_sets):
        pool = Pool()
        Endorsement = pool.get('endorsement')
        Endorsement.reset([endorsement for endorsement_set in endorsement_sets
                for endorsement in endorsement_set.endorsements])

    def get_endorsements_summary(self, name):
        summaries = []
        for endorsement in self.endorsements:
            summary = "<p align='center'> <span size='12'> <b>" + \
                    '\n'.join([x.contract_number + ' - ' + x.product.rec_name
                            + ', ' + x.subscriber.full_name
                            for x in endorsement.contracts]) + \
                    "</b> </span> </p>\n\n" + endorsement.endorsement_summary
            summaries.append(summary)

        return ('\n\n' + "<p align='center'>" + ' - ' * 30 + '</p>' +
            '\n\n').join(summaries)

    @classmethod
    def apply_set(cls, endorsement_sets):
        pool = Pool()
        Endorsement = pool.get('endorsement')
        Endorsement.apply([x for endorsement_set in endorsement_sets
                for x in endorsement_set.endorsements])

    @classmethod
    def decline_set(cls, endorsement_sets, reason=None):
        pool = Pool()
        Endorsement = pool.get('endorsement')
        Endorsement.decline([x for endorsement_set in endorsement_sets
                for x in endorsement_set.endorsements], reason=reason)

    def get_contract_set(self, name):
        if (self.endorsements and self.endorsements[0].contracts and
                self.endorsements[0].contracts[0].contract_set):
            return self.endorsements[0].contracts[0].contract_set.id

    def get_definition(self, name):
        return self.endorsements[0].definition.id

    def get_contracts(self, name):
        return [x.id for x in self.contract_set.contracts]

    @classmethod
    def search_contract_set(cls, name, clause):
        return [('endorsements.contract_endorsements.contract.contract_set',) +
            tuple(clause[1:])]

    def get_state(self, name):
        state = set([x.state for x in self.endorsements])
        assert len(state) == 1
        return state.pop()

    def get_contracts_summary(self, name):
        return '\n'.join([contract.contract_number + ' | ' +
                contract.product.rec_name
                for endorsement in self.endorsements
                for contract in endorsement.contracts])

    def get_contracts_endorsements_summary(self, name):
        return '\n'.join([endorsement.definition.rec_name for endorsement in
                self.endorsements])

    def get_subscribers_summary(self, name):
        return '\n'.join([x.get_subscribers_name(None) for x in
                self.endorsements])

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values['number']

    def get_effective_date(self, name):
        if self.endorsements:
            return self.endorsements[0].effective_date

    @classmethod
    def set_effective_date(cls, endorsement_sets, name, value):
        pool = Pool()
        Endorsement = pool.get('endorsement')
        if any([(endorsement.effective_date and
                    endorsement.effective_date != value)
                for endorsement_set in endorsement_sets
                for endorsement in endorsement_set.endorsements]):
            cls.append_functional_error('effective_date_already_set')
        to_write = []
        for endorsement_set in endorsement_sets:
            to_write += [[endorsement for endorsement in
                    endorsement_set.endorsements if (
                        not endorsement.effective_date or
                        endorsement.effective_date != value)],
                {'effective_date': value}]
        Endorsement.write(*to_write)


class Endorsement:
    __name__ = 'endorsement'

    endorsement_set = fields.Many2One('endorsement.set', 'Endorsement Set',
        ondelete='SET NULL', select=True)
    contract_set = fields.Function(
            fields.Many2One('contract.set', 'Contract Set'),
            'get_contract_set')
    generated_endorsement_sets = fields.Function(
        fields.One2Many('endorsement.set', None, 'Generated Endorsements'),
        'get_generated_endorsement_sets',
        setter='setter_void')

    @classmethod
    def __setup__(cls):
        super(Endorsement, cls).__setup__()
        cls._error_messages.update({
                'must_apply_all': 'All endorsements on endorsement set'
                ' must be applied together',
                'must_decline_all': 'All endorsements on endorsement set'
                ' must be declined together',
                })

    def get_contract_set(self, name):
        return self.endorsement_set.contract_set.id

    def get_generated_endorsement_sets(self, name):
        pool = Pool()
        EndorsementSet = pool.get('endorsement.set')
        return [x.id for x in EndorsementSet.search(
            [('endorsements.generated_by', '=', self)])]

    @classmethod
    @model.CoopView.button
    @Workflow.transition('applied')
    def apply(cls, endorsements):
        to_apply = set(endorsements)
        for endorsement in endorsements:
            if endorsement.endorsement_set and \
                    not set(endorsement.endorsement_set.endorsements
                    ).issubset(to_apply):
                cls.raise_user_error('must_apply_all')
        return super(Endorsement, cls).apply(endorsements)

    @classmethod
    def apply_for_preview(cls, endorsements):
        to_apply = []
        for endorsement in endorsements:
            to_apply.extend(endorsement.endorsement_set.endorsements)
        super(Endorsement, cls).apply_for_preview(list(set(to_apply)))

    @classmethod
    @model.CoopView.button
    @Workflow.transition('declined')
    def decline(cls, endorsements, reason=None):
        to_decline = set(endorsements)
        for endorsement in endorsements:
            if endorsement.endorsement_set and \
                    not set(endorsement.endorsement_set.endorsements
                    ).issubset(to_decline):
                cls.raise_user_error('must_decline_all')
        return super(Endorsement, cls).decline(endorsements, reason=reason)

    @classmethod
    def endorse_contracts(cls, contracts, endorsement_definition, origin=None):
        pool = Pool()
        EndorsementSet = pool.get('endorsement.set')
        all_contracts = list(contracts)
        contract_sets = defaultdict(list)
        for contract in contracts:
            if contract.contract_set:
                all_contracts.extend(contract.contract_set.contracts)
        all_contracts = list(set(all_contracts))
        endorsements = super(Endorsement, cls).endorse_contracts(
            all_contracts, endorsement_definition, origin)

        for endorsement in endorsements:
            contract_set = \
                endorsement.contract_endorsements[0].contract.contract_set
            if contract_set:
                contract_sets[contract_set].append(endorsement)

        for grouped_endorsements in contract_sets.values():
            endorsement_set = EndorsementSet()
            for endorsement in grouped_endorsements:
                endorsement.endorsement_set = endorsement_set

        cls.save(endorsements)
        return endorsements


class EndorsementSetSelectDeclineReason(model.CoopView):
    'Reason selector to decline endorsement set'

    __name__ = 'endorsement.set.decline.select_reason'

    endorsement_set = fields.Many2One('endorsement.set', 'endorsement Set',
        readonly=True)
    reason = fields.Many2One('endorsement.sub_state', 'Reason', required=True,
        domain=[('state', '=', 'declined')])


class EndorsementSetDecline(model.CoopWizard):
    'Decline EndorsementSet Wizard'

    __name__ = 'endorsement.set.decline'
    start_state = 'select_reason'
    select_reason = StateView(
        'endorsement.set.decline.select_reason',
        'endorsement_set.select_endorsement_set_decline_reason_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Apply', 'apply', 'tryton-go-next', default=True),
            ])
    apply = StateTransition()

    def default_select_reason(self, name):
        pool = Pool()
        EndorsementSet = pool.get('endorsement.set')
        assert Transaction().context.get('active_model') == 'endorsement.set'
        active_id = Transaction().context.get('active_id')
        selected_endorsement_set = EndorsementSet(active_id)
        return {
            'endorsement_set': selected_endorsement_set.id,
            }

    def transition_apply(self):
        pool = Pool()
        EndorsementSet = pool.get('endorsement.set')
        reason = self.select_reason.reason
        active_id = Transaction().context.get('active_id')
        selected_endorsement_set = EndorsementSet(active_id)
        EndorsementSet.decline_set([selected_endorsement_set], reason=reason)
        return 'end'
