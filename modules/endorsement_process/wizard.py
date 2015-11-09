from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.wizard import Button, Wizard, StateAction, StateView

from trytond.modules.process_cog import ProcessFinder, ProcessStart
from trytond.modules.cog_utils import fields, model
from trytond.modules.endorsement.endorsement import \
    STATUS_INCOMPATIBLE_WITH_ENDORSEMENTS

__metaclass__ = PoolMeta
__all__ = [
    'StartEndorsement',
    'EndorsementFindProcess',
    'EndorsementStartProcess',
    'PreviewChangesWizard',
    ]


class EndorsementFindProcess(ProcessStart):
    'Endorsement Process Finder'

    __name__ = 'endorsement.start.find_process'

    effective_date = fields.Date('Effective Date', required=True)
    definition = fields.Many2One('endorsement.definition',
        'Endorsement Definition', required=True)
    contracts = fields.Many2Many('contract', None, None,
        'Contracts', required=True, domain=[('status', 'not in',
                STATUS_INCOMPATIBLE_WITH_ENDORSEMENTS)])

    @classmethod
    def default_model(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        return Model.search([('model', '=', 'endorsement')])[0].id

    @classmethod
    def default_contracts(cls):
        pool = Pool()
        Contract = pool.get('contract')
        context_ = Transaction().context
        if context_.get('active_model', None) == 'contract':
            return [x.id for x in Contract.search([('id', 'in',
                            context_.get('active_ids', []))])]
        return []


class EndorsementStartProcess(ProcessFinder):
    'Endorsement Start Process'

    __name__ = 'endorsement.start_process'

    @classmethod
    def __setup__(cls):
        super(EndorsementStartProcess, cls).__setup__()
        cls._error_messages.update({
                'single_contract_definition': 'The chosen endorsement '
                'definition cannot be applied on several contracts.',
                })

    @classmethod
    def get_parameters_model(cls):
        return 'endorsement.start.find_process'

    @classmethod
    def get_parameters_view(cls):
        return \
            'endorsement_process.endorsement_start_process_find_process_form'

    def init_main_object_from_process(self, obj, process_param):
        pool = Pool()
        ContractEndorsement = pool.get('endorsement.contract')
        if (not process_param.definition.is_multi_instance and
                len(process_param.contracts) > 1):
            self.raise_user_error('single_contract_definition')
        res, errs = super(EndorsementStartProcess,
            self).init_main_object_from_process(obj, process_param)
        obj.effective_date = process_param.effective_date
        obj.definition = process_param.definition
        obj.contract_endorsements = [ContractEndorsement(contract=contract)
            for contract in process_param.contracts]
        return res, errs


class PreviewChangesWizard(Wizard):
    'Preview Changes'

    __name__ = 'endorsement.preview_changes'

    start_state = 'launch'

    launch = StateAction('endorsement.act_start_endorsement')

    def do_launch(self, action):
        return action, {'extra_context': {'only_preview': True},
            'model': 'endorsement',
            'id': Transaction().context.get('active_id'),
            'ids': [Transaction().context.get('active_id')],
            }


class StartEndorsement:
    'Start Endorsement'

    __name__ = 'endorsement.start'

    @classmethod
    def __setup__(cls):
        super(StartEndorsement, cls).__setup__()
        for attribute in dir(cls):
            if not isinstance(getattr(cls, attribute), StateView):
                continue
            for button in getattr(cls, attribute).buttons:
                if 'preview' in attribute:
                    getattr(cls, attribute).buttons = [Button(string='Ok',
                            state='end', icon='tryton-ok', default=True)]
                else:
                    getattr(cls, attribute).buttons = [x for x in
                        getattr(cls, attribute).buttons if x.string !=
                        'Apply']

    def get_next_state(self, current_state):
        found = False
        for part in self.definition.endorsement_parts:
            if part.view == current_state:
                found = True
            elif found:
                return part.view
        return 'end'

    def transition_start(self):
        pool = Pool()
        EndorsementPartUnion = pool.get('endorsement.part.union')
        Endorsement = pool.get('endorsement')

        if Transaction().context.get('only_preview') is True:
            super(StartEndorsement, self).transition_start()
            return 'preview_changes'
        else:
            active_model = Transaction().context.get('active_model')
            if active_model == 'endorsement.part.union':
                endorsement = EndorsementPartUnion(
                        Transaction().context.get('active_id')).endorsement
            elif active_model == 'endorsement.contract':
                # See the explanation in the table_query method on
                # endorsement.part.union model
                # in endorsement_process/endorsement.py
                endorsement = Endorsement(
                    Transaction().context.get('active_id') / 100)
            else:
                return super(StartEndorsement, self).transition_start()
            if endorsement.state == 'applied':
                self.raise_user_error('cannot_resume_applied')
            self.select_endorsement.endorsement = endorsement
            if endorsement.contracts:
                self.select_endorsement.contract = endorsement.contracts[0].id
                self.select_endorsement.product = \
                    endorsement.contracts[0].product.id
            self.select_endorsement.effective_date = endorsement.effective_date
            self.select_endorsement.endorsement_definition = \
                endorsement.definition.id
            return 'start_endorsement'

    def transition_start_endorsement(self):
        pool = Pool()
        EndorsementPart = pool.get('endorsement.part')
        if Transaction().context.get(
                'active_model') != 'endorsement.part.union':
            return super(StartEndorsement, self).transition_start_endorsement()
        with model.error_manager():
            self.check_before_start()
        if not self.endorsement:
            endorsement = Pool().get('endorsement')()
            endorsement.effective_date = \
                self.select_endorsement.effective_date
            endorsement.definition = self.definition
            if self.select_endorsement.applicant:
                endorsement.applicant = self.select_endorsement.applicant
            endorsement.save()
            self.select_endorsement.endorsement = endorsement.id
        # See the explanation in the table_query method on
        # endorsement.part.union model in endorsement_process/endorsement.py
        return EndorsementPart(Transaction().context.get(
                'active_id') % 100).view
