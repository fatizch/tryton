from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pyson import Eval, Bool, And, Not, Len, If

from trytond.modules.cog_utils import model, coop_string, fields

__all__ = [
    'SelectEndorsement',
    'PreviewChanges',
    'StartEndorsement',
    'EndorsementWizardStepMixin',
    'EndorsementWizardStepVersionedObjectMixin',
    ]


class EndorsementWizardStepMixin(object):
    '''
        A mixin class for State Views being used in the Endorsement Wizard.
        They store basic information about the current endorsement :
            - effective_date : the effective date at which the endorsement
                takes place
            - endorsement_definition : the endorsement being created
            - endorsement_part : the endorsement_part the current state view
                is being related to.
    '''
    effective_date = fields.Date('Effective Date', states={
            'readonly': True})
    endorsement_definition = fields.Many2One('endorsement.definition',
        'Endorsement Definition', states={'readonly': True})
    endorsement_part = fields.Many2One('endorsement.part',
        'Endorsement Part', states={'invisible': True, 'readonly': True})

    def update_endorsement(self, endorsement, wizard):
        # Updates the current endorsement using the data provided in the
        # current instance of the wizard
        raise NotImplementedError


class EndorsementWizardStepVersionedObjectMixin(EndorsementWizardStepMixin):
    '''
        Mixin used in the particular case of endorsement manipulating
        revision_mixin_instances.

        This mixin provides an easy access to the current / future values of
        the field being modified. It also add an option to delete
        future instances.

        It also provides helper methods for easy default values and
        endorsement instance update.
    '''
    _target_model = None

    current_value = fields.One2Many(None, None, 'Current Value', readonly=True)
    delete_future = fields.Boolean('Delete Future Modifications', states={
            'invisible': Len(Eval('future_value', [])) <= 0},
        depends=['future_value'])
    future_value = fields.One2Many(None, None, 'Future Value', readonly=True,
        states={'invisible': Len(Eval('future_value', [])) <= 0},
        depends=['future_value'])
    new_value = fields.One2Many(None, None, 'New Value')

    @classmethod
    def __setup__(cls):
        cls.current_value.model_name = cls._target_model
        cls.future_value.model_name = cls._target_model
        cls.new_value.model_name = cls._target_model
        super(EndorsementWizardStepVersionedObjectMixin, cls).__setup__()


class SelectEndorsement(model.CoopView):
    'Select Endorsement'

    __name__ = 'endorsement.start.select_endorsement'

    applicant = fields.Many2One('party.party', 'Applicant')
    contract = fields.Many2One('contract', 'Contract')
    effective_date = fields.Date('Effective Date')
    endorsement = fields.Many2One('endorsement', 'Endorsement',
        states={'invisible': True})
    endorsement_definition = fields.Many2One('endorsement.definition',
        'Endorsement', domain=[
            If(Bool(Eval('product', False)),
                [('products', '=', Eval('product'))],
                [('products', '=', None)])],
        depends=['product'])
    product = fields.Many2One('offered.product', 'Product', readonly=True)

    @fields.depends('contract')
    def on_change_contract(self):
        return {'product': self.contract.product.id if self.contract else None}


class PreviewChanges(model.CoopView):
    'Preview changes'

    __name__ = 'endorsement.start.preview_changes'

    @classmethod
    def get_default_values_from_changes(cls, changes):
        return {}


class StartEndorsement(Wizard):
    'Start Endorsement'

    __name__ = 'endorsement.start'

    start_state = 'start'
    start = StateTransition()
    select_endorsement = StateView('endorsement.start.select_endorsement',
        'endorsement.select_endorsement_view_form', [
            Button('Cancel', 'cancel', 'tryton-cancel'),
            Button('Start Endorsement', 'start_endorsement',
                'tryton-go-next', default=True, states={
                    'readonly': Not(And(
                            Bool(Eval('contract', False)),
                            Bool(Eval('effective_date', False)),
                            Bool(Eval('endorsement_definition', False))))})])
    cancel = StateTransition()
    suspend = StateTransition()
    start_endorsement = StateTransition()
    summary = StateView('endorsement.start.select_endorsement',
        'endorsement.endorsement_summary_view_form', [
            Button('Previous', 'summary_previous', 'tryton-go-previous'),
            Button('Save', 'suspend', 'tryton-save'),
            Button('Cancel', 'cancel', 'tryton-cancel'),
            Button('Preview', 'preview_changes', 'tryton-text-markup'),
            Button('Apply', 'apply_endorsement', 'tryton-go-next',
                default=True)])
    apply_endorsement = StateTransition()
    summary_previous = StateTransition()
    preview_changes = StateView('endorsement.start.preview_changes',
        'endorsement.preview_changes_view_form', [
            Button('Summary', 'summary', 'tryton-go-previous'),
            Button('Cancel', 'cancel', 'tryton-cancel'),
            Button('Apply', 'apply_endorsement', 'tryton-go-next',
                default=True),
            ])

    @property
    def definition(self):
        if not self.select_endorsement:
            return None
        return self.select_endorsement.endorsement_definition

    @property
    def endorsement(self):
        if not self.select_endorsement:
            return None
        return self.select_endorsement.endorsement

    def transition_start(self):
        if Transaction().context.get('active_model') != 'endorsement':
            return 'select_endorsement'
        endorsement = Pool().get('endorsement')(
            Transaction().context.get('active_id'))
        self.select_endorsement.endorsement = endorsement.id
        self.select_endorsement.contract = endorsement.contracts[0].id
        self.select_endorsement.effective_date = endorsement.effective_date
        self.select_endorsement.product = endorsement.contracts[0].product.id
        self.select_endorsement.endorsement_definition = \
            endorsement.definition.id
        return 'start_endorsement'

    def default_select_endorsement(self, name):
        if self.select_endorsement._default_values:
            return self.select_endorsement._default_values
        pool = Pool()
        Date = pool.get('ir.date')
        if Transaction().context.get('active_model') == 'contract':
            contract = pool.get('contract')(
                Transaction().context.get('active_id'))
            return {
                'effective_date': max(contract.start_date, Date.today()),
                'contract': contract.id,
                'applicant': contract.subscriber.id,
                }
        return {'effective_date': Date.today()}

    def transition_cancel(self):
        if self.endorsement:
            Pool().get('endorsement').delete([self.endorsement])
        return 'end'

    def transition_suspend(self):
        return 'end'

    def transition_start_endorsement(self):
        if not self.endorsement:
            endorsement = Pool().get('endorsement')()
            endorsement.effective_date = \
                self.select_endorsement.effective_date
            endorsement.definition = self.definition
            if self.select_endorsement.applicant:
                endorsement.applicant = self.select_endorsement.applicant
            endorsement.save()
            self.select_endorsement.endorsement = endorsement.id
        return self.definition.endorsement_parts[0].view

    def default_summary(self, name):
        result = self.select_endorsement._default_values
        return result

    def default_preview_changes(self, name):
        PreviewChanges = Pool().get('endorsement.start.preview_changes')
        changes = self.endorsement.extract_preview_values()
        return PreviewChanges.get_default_values_from_changes(changes)

    def transition_summary_previous(self):
        return self.get_state_before('')

    def transition_apply_endorsement(self):
        Pool().get('endorsement').apply([self.endorsement])
        return 'end'

    def get_state_before(self, state_name):
        for part in reversed(self.definition.endorsement_parts):
            if not state_name:
                return part.view
            if part.view == state_name:
                state_name = ''
        return 'start'

    def get_next_state(self, current_state):
        found = False
        for part in self.definition.endorsement_parts:
            if part.view == current_state:
                found = True
            elif found:
                return part.view
        return 'summary'

    @classmethod
    def get_endorsement_states(cls):
        # Returns the endorsement wizard specific state views
        pool = Pool()
        result = {}
        for state_name, state in cls.states.iteritems():
            if not issubclass(state.__class__, StateView):
                continue
            state_class = pool.get(state.model_name)
            if not issubclass(state_class, EndorsementWizardStepMixin):
                continue
            result[state_name] = coop_string.translate_model_name(
                pool.get(state.model_name))
        return result
