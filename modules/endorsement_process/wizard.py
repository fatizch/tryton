from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.wizard import Button, Wizard, StateAction, StateView

from trytond.modules.process_cog import ProcessFinder, ProcessStart
from trytond.modules.cog_utils import fields

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
    definition = fields.Many2One('endorsement.definition', 'Definition')
    contracts = fields.Many2Many('contract', None, None,
        'Contracts')

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'endorsement')])[0].id

    @classmethod
    def build_process_domain(cls):
        result = super(
            EndorsementFindProcess, cls).build_process_domain()
        return result


class EndorsementStartProcess(ProcessFinder):
    'Endorsement Start Process'

    __name__ = 'endorsement.start_process'

    @classmethod
    def get_parameters_model(cls):
        return 'endorsement.start.find_process'

    @classmethod
    def get_parameters_view(cls):
        return \
            'endorsement_process.endorsement_start_process_find_process_form'

    def init_main_object_from_process(self, obj, process_param):
        pool = Pool()
        EndorsementContract = pool.get('endorsement.contract')
        res, errs = super(EndorsementStartProcess,
            self).init_main_object_from_process(obj, process_param)
        obj.definition = process_param.definition
        obj.save()
        contract_endorsements = []
        contract_endorsements = EndorsementContract.create([{
                    'contract': contract.id,
                    'endorsement': obj.id,
                    } for contract in process_param.contracts])
        obj.contract_endorsements = contract_endorsements
        obj.effective_date = process_param.effective_date
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
                    Transaction().context.get('active_id') / 100000)
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
                'active_id') % 100000).view
