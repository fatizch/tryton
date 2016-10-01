# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import model, fields, utils
from trytond.modules.endorsement import (EndorsementWizardStepMixin,
    add_endorsement_step)

__metaclass__ = PoolMeta
__all__ = [
    'StartFullContractRevision',
    'StartEndorsement',
    ]


class StartFullContractRevision(EndorsementWizardStepMixin):
    'Start Full Contract Revision'

    __name__ = 'endorsement.contract.full_revision_start'

    current_start_date = fields.Date('Current Start Date', readonly=True)
    start_date = fields.Date('New Start Date', readonly=True)

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(StartFullContractRevision, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract' and utils.is_module_installed(
                'endorsement_insurance_invoice'):
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(StartFullContractRevision,
            cls).get_draft_methods_for_model(model_name)
        if model_name == 'contract' and utils.is_module_installed(
                'endorsement_insurance_invoice'):
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods

    @classmethod
    def state_view_name(cls):
        return 'endorsement_full_contract_revision.' + \
            'full_contract_revision_view_form'

    def step_default(self, name):
        defaults = super(StartFullContractRevision, self).step_default()
        contracts = self._get_contracts()
        if len(contracts) != 1:
            self.raise_user_error('only_one_contract')
        endorsement = contracts.values()[0]
        defaults['current_start_date'] = endorsement.contract.start_date
        defaults['start_date'] = self.effective_date
        return defaults

    def step_next(self):
        super(StartFullContractRevision, self).step_next()

        Contract = Pool().get('contract')
        contracts = self._get_contracts()

        # Create a snapshot to revert back to
        self.wizard.endorsement.in_progress([self.wizard.endorsement])

        # Clean up contract
        contract = Contract(contracts.keys()[0])
        if self.start_date and (self.start_date != self.current_start_date):
            contract.start_date = self.start_date
            contract.save()
        Contract.revert_to_project([contract])

        # Everything else will be taken care of in
        # do_full_contract_revision_action
        return 'full_contract_revision_action'

    def step_update(self):
        contracts = self._get_contracts()
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
            active_id = Transaction().context.get('active_id')
            if not active_id:
                return 'end'
            endorsement = Pool().get('endorsement')(active_id)
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
        candidates = []
        if utils.is_module_installed('offered_insurance'):
            candidates = Process.search([
                    ('on_model.model', '=', 'contract'),
                    ('kind', '=', 'full_contract_revision'),
                    ('for_products', '=', contract.product.id),
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

        return values[0], {'res_id': [contract.id]}

    def do_resume_contract_process(self, action):
        endorsement = Pool().get('endorsement')(
            Transaction().context.get('active_id'))
        contract_id = endorsement.contract_endorsements[0].contract.id
        return (action, {
                'id': contract_id,
                'model': 'contract',
                'res_id': [contract_id],
                'res_model': 'contract',
                })


add_endorsement_step(StartEndorsement, StartFullContractRevision,
    'full_contract_revision')
