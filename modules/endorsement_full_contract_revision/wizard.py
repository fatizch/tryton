from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.wizard import StateView, StateTransition, Button

from trytond.modules.cog_utils import model, fields
from trytond.modules.endorsement import EndorsementWizardStepMixin

__metaclass__ = PoolMeta
__all__ = [
    'StartFullContractRevision',
    'StartEndorsement',
    ]


class StartFullContractRevision(EndorsementWizardStepMixin, model.CoopView):
    'Start Full Contract Revision'

    __name__ = 'endorsement.contract.full_revision_start'

    current_start_date = fields.Date('Current Start Date', readonly=True)
    new_start_date = fields.Date('New Start Date')

    def update_endorsement(self, base_endorsement, wizard):
        base_endorsement.values = {
            'start_date': self.new_start_date or self.current_start_date,
            }
        base_endorsement.save()

    @classmethod
    def update_default_values(cls, wizard, base_endorsement, default_values):
        return {
            'new_start_date': base_endorsement.values.get('start_date', None),
            }


class StartEndorsement:
    __name__ = 'endorsement.start'

    full_contract_revision = StateView(
        'endorsement.contract.full_revision_start',
        'endorsement_full_contract_revision.full_contract_revision_view_form',
        [Button('Previous', 'full_contract_revision_previous',
                'tryton-go-previous'),
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Next', 'full_contract_revision_next', 'tryton-go-next',
                default=True)])
    full_contract_revision_previous = StateTransition()
    full_contract_revision_next = StateTransition()
    full_contract_revision_action = model.VoidStateAction()
    resume_contract_process = model.StateAction(
        'process_cog.act_resume_process')

    @classmethod
    def __setup__(cls):
        super(StartEndorsement, cls).__setup__()
        cls._error_messages.update({
                'no_process_found': 'Cannot start full contract revision, '
                'no matching process available',
                })

    def transition_start(self):
        if Transaction().context.get('active_model') == 'endorsement':
            endorsement = Pool().get('endorsement')(
                Transaction().context.get('active_id'))
            xml_id = 'endorsement_full_contract_revision.'
            'full_contract_revision_definition'
            if endorsement.definition.xml_id == xml_id:
                return 'resume_contract_process'
        return super(StartEndorsement, self).transition_start()

    def transition_full_contract_revision_previous(self):
        self.end_current_part('full_contract_revision')
        return self.get_state_before('full_contract_revision')

    def default_full_contract_revision(self, name):
        State = Pool().get('endorsement.contract.full_revision_start')
        contract = self.select_endorsement.contract
        endorsement_part = self.get_endorsement_part_for_state(
            'full_contract_revision')
        endorsement_date = self.select_endorsement.effective_date
        result = {
            'endorsement_definition': self.definition.id,
            'endorsement_part': endorsement_part.id,
            'effective_date': endorsement_date,
            'current_start_date': contract.start_date,
            }
        if self.endorsement and self.endorsement.contract_endorsements:
            result.update(State.update_default_values(self,
                    self.endorsement.contract_endorsements[0], result))
        else:
            result['new_start_date'] = self.select_endorsement.effective_date
        return result

    def transition_full_contract_revision_next(self):
        Contract = Pool().get('contract')

        # End endorsement state as usual
        self.end_current_part('full_contract_revision')

        # Create a snapshot to revert back to
        self.endorsement.in_progress([self.endorsement])

        # Clean up contract
        contract = Contract(self.select_endorsement.contract.id)
        state = self.full_contract_revision
        if state.new_start_date and (
                state.new_start_date != state.current_start_date):
            contract.set_start_date(state.new_start_date)
            contract.save()
        Contract.revert_to_project([contract])

        # Everything else will be taken care of in
        # do_full_contract_revision_action
        return 'full_contract_revision_action'

    def do_full_contract_revision_action(self, action):
        pool = Pool()
        Action = pool.get('ir.action')
        Contract = pool.get('contract')
        Process = pool.get('process')
        contract = Contract(self.select_endorsement.contract.id)

        # Find suitable process
        candidates = Process.search([
                ('on_model.model', '=', 'contract'),
                ('kind', '=', 'full_contract_revision'),
                ])
        if not candidates:
            candidates = Process.search([
                    ('on_model.model', '=', 'contract'),
                    ('kind', '=', 'full_contract_revision'),
                    ])
        if not candidates:
            self.raise_user_error('no_process_found')

        process = candidates[0]
        action = process.get_act_window()
        values = Action.get_action_values('ir.action.act_window', [action.id])
        values[0]['views'] = [view for view in values[0]['views']
            if view[1] == 'form']

        # Update contract state
        contract.current_state = process.all_steps[0]
        contract.current_state.step.execute_before(contract)
        contract.save()

        return values[0], {'res_id': contract.id}

    def do_resume_contract_process(self, action):
        endorsement = Pool().get('endorsement')(
            Transaction().context.get('active_id'))
        contract_id = endorsement.contract_endorsements[0].contract.id
        return (action, {
                'id': contract_id,
                'model': 'contract',
                'res_id': contract_id,
                'res_model': 'contract',
                })
