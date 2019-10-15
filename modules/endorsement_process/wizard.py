# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval
from trytond.wizard import Wizard, StateAction, StateView, Button, \
        StateTransition
from trytond.server_context import ServerContext

from trytond.modules.process_cog.process import ProcessFinder, ProcessStart
from trytond.modules.coog_core import fields, model
from trytond.modules.endorsement.endorsement import \
    STATUS_INCOMPATIBLE_WITH_ENDORSEMENTS

__all__ = [
    'StartEndorsement',
    'EndorsementFindProcess',
    'EndorsementStartProcess',
    'PreviewChangesWizard',
    'AskNextEndorsementChoice',
    'AskNextEndorsement',
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
            raise ValidationError(gettext(
                    'endorsement_process.msg_single_contract_definition'))
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


class StartEndorsement(metaclass=PoolMeta):
    'Start Endorsement'
    __name__ = 'endorsement.start'

    @classmethod
    def __setup__(cls):
        super(StartEndorsement, cls).__setup__()
        for attribute in dir(cls):
            if not isinstance(getattr(cls, attribute), StateView):
                continue
            for button in getattr(cls, attribute).buttons:
                states = button.states.get('invisible', None)
                if button.state.endswith('_next'):
                    continue
                if button.state.endswith('_suspend'):
                    continue
                if states is None:
                    button.states['invisible'] = Bool(Eval('context',
                        {}).get('only_preview', False))
                else:
                    button.states['invisible'] |= Bool(Eval('context',
                        {}).get('only_preview', False))
            if 'preview' in attribute:
                getattr(cls, attribute).buttons.append(Button(string='Ok',
                        state='end', icon='tryton-ok', default=True,
                        states={'invisible': ~Bool(Eval('context',
                            {}).get('only_preview', False))}))

    def get_next_state(self, current_state):
        if not self.endorsement or not self.endorsement.current_state:
            return super(StartEndorsement, self).get_next_state(current_state)
        return self.get_next_view_or_end(current_state)

    def get_next_view_or_end(self, current_state):
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
                raise ValidationError(
                    gettext('endorsement.msg_cannot_resume_applied'))
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
            self.select_endorsement.init_new_endorsement()
        # See the explanation in the table_query method on
        # endorsement.part.union model in endorsement_process/endorsement.py
        return EndorsementPart(Transaction().context.get(
                'active_id') % 100).view


class AskNextEndorsementChoice(model.CoogView):
    'Ask Next Endorsement Choice'

    __name__ = 'endorsement.ask_next_endorsement.choice'

    question = fields.Text('Question', readonly=True)


class AskNextEndorsement(model.CoogWizard):
    'Ask For Next Endorsement Wizard'

    __name__ = 'endorsement.ask_next_endorsement'

    start_state = 'detect'
    detect = StateTransition()
    choice = StateView('endorsement.ask_next_endorsement.choice',
        'endorsement_process.endorsement_ask_next_endorsement_choice_view_form',
            [Button('No', 'apply_without_generate', 'tryton-cancel'),
                Button('Generate', 'apply_with_generate', 'tryton-go-next',
                    default=True)])
    apply_without_generate = StateTransition()
    apply_with_generate = StateTransition()

    def get_endorsement(self):
        active_model = Transaction().context.get('active_model', None)
        if active_model != 'endorsement':
            return
        active_id = Transaction().context.get('active_id')
        if not active_id:
            return
        Endorsement = Pool().get('endorsement')
        return Endorsement(active_id)

    def transition_detect(self):
        endorsement = self.get_endorsement()
        if not endorsement.definition.next_endorsement:
            return 'apply_without_generate'
        return 'choice'

    def default_choice(self, name):
        endorsement = self.get_endorsement()
        next_endorsement = endorsement.definition.next_endorsement.rec_name
        return {
            'question': gettext(
                'endorsement_process.msg_ask_next_endorsement',
                next_endorsement=next_endorsement),
            }

    def transition_apply_without_generate(self):
        Endorsement = Pool().get('endorsement')
        endorsement = self.get_endorsement()
        with ServerContext().set_context(force_contracts_to_endorse=False):
            with Transaction().set_context(force_synchronous=True):
                Endorsement.apply([endorsement])
                return 'end'

    def transition_apply_with_generate(self):
        with ServerContext().set_context(force_contracts_to_endorse=True):
            with Transaction().set_context(force_synchronous=True):
                Pool().get('endorsement').apply([self.get_endorsement()])
                return 'end'

    def end(self):
        return 'reload'
