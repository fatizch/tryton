from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import model, fields
from trytond.modules.endorsement import (EndorsementWizardStepMixin,
    add_endorsement_step)

__metaclass__ = PoolMeta
__all__ = [
    'StartFullContractRevision',
    'StartEndorsement',
    ]


class StartFullContractRevision(EndorsementWizardStepMixin, model.CoopView):
    'Start Full Contract Revision'

    __name__ = 'endorsement.contract.full_revision_start'

    current_start_date = fields.Date('Current Start Date', readonly=True)
    start_date = fields.Date('New Start Date')

    @classmethod
    def state_view_name(cls):
        return 'endorsement_full_contract_revision.' + \
            'full_contract_revision_view_form'

    def step_default(self, wizard, step_name, name):
        defaults = super(StartFullContractRevision, self).step_default(wizard,
            step_name, name)
        contracts = self._get_contracts(wizard)
        if len(contracts) != 1:
            self.raise_user_error('only_one_contract')
        endorsement = contracts.values()[0]
        defaults['current_start_date'] = endorsement.contract.start_date
        defaults.update(self._get_default_values(endorsement.values,
                endorsement.contract, ['start_date']))
        return defaults

    def step_next(self, wizard, step_name):
        super(StartFullContractRevision, self).step_next(wizard,
            step_name)

        Contract = Pool().get('contract')
        contracts = self._get_contracts(wizard)

        # Create a snapshot to revert back to
        wizard.endorsement.in_progress([wizard.endorsement])

        # Clean up contract
        contract = Contract(contracts.keys()[0])
        if self.start_date and (self.start_date != self.current_start_date):
            contract.set_start_date(self.start_date)
            contract.save()
        Contract.revert_to_project([contract])

        # Everything else will be taken care of in
        # do_full_contract_revision_action
        return 'full_contract_revision_action'

    def step_update(self, wizard):
        contracts = self._get_contracts(wizard)
        endorsement = contracts.values()[0]
        if self._update_values(self, endorsement.contract, endorsement.values,
                ['start_date']):
            endorsement.save()


class StartEndorsement:
    __name__ = 'endorsement.start'

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


add_endorsement_step(StartEndorsement, StartFullContractRevision,
    'full_contract_revision')
