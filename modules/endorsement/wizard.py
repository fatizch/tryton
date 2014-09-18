from collections import defaultdict

from trytond.pool import Pool
from trytond.model import Model
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.wizard import StateAction
from trytond.pyson import Eval, Bool, And, Not, Len, If, PYSONEncoder

from trytond.modules.cog_utils import model, coop_string, fields

__all__ = [
    'SelectEndorsement',
    'BasicPreview',
    'StartEndorsement',
    'OpenContractAtApplicationDate',
    'EndorsementWizardStepMixin',
    'EndorsementWizardStepBasicObjectMixin',
    'EndorsementWizardStepVersionedObjectMixin',
    'EndorsementWizardPreviewMixin',
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


class EndorsementWizardStepBasicObjectMixin(EndorsementWizardStepMixin):
    '''
        Mixin used for modifying an object. It displays the current instance
        (before endorsement) next to the modified version.

        It includes basic methods for default values and instance update
    '''
    _target_model = None

    current_value = fields.One2Many(None, None, 'Current Value', readonly=True)
    new_value = fields.One2Many(None, None, 'New Value')

    @classmethod
    def __setup__(cls):
        cls.current_value.model_name = cls._target_model
        cls.new_value.model_name = cls._target_model
        super(EndorsementWizardStepBasicObjectMixin, cls).__setup__()

    def _update_endorsement(self, endorsement, values_field):
        if getattr(endorsement, 'values', None) is None:
            endorsement.values = {}
        for endorsed_field in getattr(self.endorsement_part, values_field):
            new_value = getattr(self.new_value[0], endorsed_field.name, None)
            if isinstance(new_value, Model):
                new_value = new_value.id
            endorsement.values[endorsed_field.name] = new_value

        # Make sure "save" will be triggered
        endorsement.values = endorsement.values

    @classmethod
    def update_new_value_from_endorsement(cls, endorsement, value,
            endorsement_part, value_field):
        for endorsed_field in getattr(endorsement_part, value_field):
            if not endorsed_field.name in endorsement.values:
                continue
            value[endorsed_field.name] = endorsement.values[
                endorsed_field.name]

    @classmethod
    def get_state_view_default_values(cls, wizard, endorsed_field_view,
            endorsed_model, state_name, endorsement_part_field):
        pool = Pool()
        View = pool.get('ir.ui.view')
        good_view, = View.search([('xml_id', '=', endorsed_field_view)])
        endorsed_fields = wizard.get_fields_to_get(endorsed_model, good_view.id)
        endorsement_part = wizard.get_endorsement_part_for_state(state_name)
        endorsed_object = wizard.get_endorsed_object(endorsement_part)
        endorsement_date = wizard.select_endorsement.effective_date
        result = {
            'endorsement_part': endorsement_part.id,
            'effective_date': endorsement_date,
            'endorsement_definition':
            wizard.select_endorsement.endorsement_definition.id,
            }
        result['current_value'] = [endorsed_object.id]
        result['new_value'] = [wizard.get_new_instance_fields(endorsed_object,
                endorsed_fields)]
        endorsements = wizard.get_endorsements_for_state(state_name)
        if endorsements:
            # TODO : multi targets ?
            endorsement = endorsements[0]
            cls.update_new_value_from_endorsement(endorsement,
                result['new_value'][0], endorsement_part,
                endorsement_part_field)
        return result


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


class EndorsementWizardPreviewMixin(object):
    '''
        This mixin class is used to create Preview typed State Views.
        It requires to override a method which will be used to calculate
        the before / after values
    '''

    @classmethod
    def extract_endorsement_preview(cls, instance):
        raise NotImplementedError


class SelectEndorsement(model.CoopView):
    'Select Endorsement'

    __name__ = 'endorsement.start.select_endorsement'

    applicant = fields.Many2One('party.party', 'Applicant')
    contract = fields.Many2One('contract', 'Contract')
    effective_date = fields.Date('Effective Date', states={
            'invisible': ~Bool(Eval('endorsement_definition', False))})
    endorsement = fields.Many2One('endorsement', 'Endorsement',
        states={'invisible': True})
    endorsement_definition = fields.Many2One('endorsement.definition',
        'Endorsement', domain=['OR',
            If(Bool(Eval('product', False)),
                [('products', '=', Eval('product'))],
                []),
            [('products', '=', None)]],
        depends=['product'])
    endorsement_summary = fields.Text('Endorsement Summary')
    product = fields.Many2One('offered.product', 'Product', readonly=True)
    has_preview = fields.Boolean('Has Preview', readonly=True)

    @fields.depends('contract')
    def on_change_contract(self):
        return {'product': self.contract.product.id if self.contract else None}


class BasicPreview(EndorsementWizardPreviewMixin, model.CoopView):
    'Basic Preview State View'

    __name__ = 'endorsement.start.preview_changes'

    @classmethod
    def get_fields_to_get(cls):
        # Returns a list of fields grouped per model name which will be
        # used to calculate before / after values
        return defaultdict(set)

    @classmethod
    def extract_endorsement_preview(cls, instance):
        return dict([(field_name, getattr(instance, field_name, None))
                for field_name in cls.get_fields_to_get()[instance.__name__]])

    @classmethod
    def init_from_preview_values(cls, preview_values):
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
            Button('Preview', 'preview_changes', 'tryton-text-markup',
                states={'invisible': ~Eval('has_preview')}),
            Button('Apply', 'apply_endorsement', 'tryton-go-next',
                default=True)])
    apply_endorsement = StateTransition()
    summary_previous = StateTransition()
    preview_changes = StateTransition()
    basic_preview = StateView('endorsement.start.preview_changes',
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
        self.select_endorsement.endorsement = endorsement
        if endorsement.contracts:
            self.select_endorsement.contract = endorsement.contracts[0].id
            self.select_endorsement.product = \
                endorsement.contracts[0].product.id
        self.select_endorsement.effective_date = endorsement.effective_date
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
        result['endorsement_summary'] = \
            self.endorsement.endorsement_summary
        result['has_preview'] = self.endorsement.definition.preview_state != ''
        return result

    def transition_summary_previous(self):
        return self.get_state_before('')

    def transition_preview_changes(self):
        return self.endorsement.definition.preview_state

    def default_basic_preview(self, name):
        BasicPreview = Pool().get('endorsement.start.preview_changes')
        preview_values = self.endorsement.extract_preview_values(
            BasicPreview.extract_endorsement_preview)
        return BasicPreview.init_from_preview_values(preview_values)

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

    def get_endorsement_part_for_state(self, state_name):
        definition = self.select_endorsement.endorsement_definition
        for part in definition.endorsement_parts:
            if part.view == state_name:
                return part

    def get_endorsements_for_state(self, state_name):
        endorsement_part = self.get_endorsement_part_for_state(state_name)
        return self.endorsement.find_parts(endorsement_part)

    def set_main_object(self, endorsement):
        # TODO : update once endorsement parts are applied on different models
        endorsement.contract = self.select_endorsement.contract
        endorsement.options = []

    def get_clean_endorsement(self, state):
        current_part = state.endorsement_part
        endorsements = self.endorsement.find_parts(current_part)
        if not endorsements:
            endorsements = [self.endorsement.new_endorsement(
                    current_part)]
            self.set_main_object(endorsements[0])
        else:
            [current_part.clean_up(endorsement)
                for endorsement in endorsements]
        return endorsements[0]

    def end_current_part(self, state_name):
        state = getattr(self, state_name)
        endorsement = self.get_clean_endorsement(state)
        state.update_endorsement(endorsement, self)
        endorsement.save()

    def get_endorsed_object(self, endorsement_part):
        # TODO : Update once multiple objects may be changed
        return self.select_endorsement.contract

    @classmethod
    def get_fields_to_get(cls, model, view_id):
        fields_def = Pool().get(model).fields_view_get(view_id)
        return fields_def['fields'].iterkeys()

    @classmethod
    def get_new_instance_fields(cls, base_instance, fields):
        result = {}
        for field_name in fields:
            value = getattr(base_instance, field_name)
            if isinstance(value, (list, tuple)):
                result[field_name] = [x.id for x in value]
            else:
                result[field_name] = getattr(value, 'id', value)
        return result

    @classmethod
    def update_defaults_from_endorsement(cls, result, endorsement,
            endorsed_field_name):
        new_value = result['new_value'][0]
        for elem in getattr(endorsement, endorsed_field_name):
            if elem.action in ('add', 'update'):
                new_value.update(elem.values)
            elif elem.action == 'remove':
                result['delete_future'] = True

    def update_revision_endorsement(self, state, endorsement,
            endorsed_field_name):
        EndorsementModel = Pool().get(
            endorsement._fields[endorsed_field_name].model_name)
        endorsed_object = self.get_endorsed_object(state.endorsement_part)
        EndorsementModel.delete(
            list(getattr(endorsement, endorsed_field_name, [])))
        result = []
        if state.delete_future:
            to_delete = [EndorsementModel(action='remove', relation=x.id)
                for x in getattr(endorsed_object, endorsed_field_name)
                if x.date and x.date > self.select_endorsement.effective_date]
            result += to_delete
        result.append(EndorsementModel(action='add',
                values=dict(state.new_value[0]._save_values)))
        setattr(endorsement, endorsed_field_name, result)

    def update_add_to_list_endorsement(self, state, endorsement,
            endorsed_field_name):
        EndorsementModel = Pool().get(
            endorsement._fields[endorsed_field_name].model_name)
        EndorsementModel.delete([x for x in getattr(endorsement,
                    endorsed_field_name, []) if x.action == 'add'])

        def filter_values(values):
            keys = [x.name for x in getattr(state.endorsement_part,
                    endorsed_field_name + '_fields')]
            to_del = [k for k in values.iterkeys() if k not in keys]
            for k in to_del:
                values.pop(k)
            return values

        setattr(endorsement, endorsed_field_name, [
                EndorsementModel(action='add', values=filter_values(
                        value._save_values))
                for value in getattr(state, endorsed_field_name, [])])

    def get_revision_state_defaults(self, state_name, endorsed_model,
            endorsed_field_name, endorsed_field_view):
        pool = Pool()
        View = pool.get('ir.ui.view')
        good_view, = View.search([('xml_id', '=', endorsed_field_view)])
        endorsed_fields = self.get_fields_to_get(endorsed_model, good_view.id)
        endorsement_part = self.get_endorsement_part_for_state(state_name)
        endorsed_object = self.get_endorsed_object(endorsement_part)
        endorsement_date = self.select_endorsement.effective_date
        current, future = None, None
        for value in getattr(endorsed_object, endorsed_field_name):
            if not value.date:
                current = value
                continue
            if (not current.date or value.date >= current.date) and (
                    value.date <= endorsement_date):
                current = value
                continue
            if value.date > endorsement_date:
                future = value
                break
        result = {
            'new_value': [{}],
            'current_value': [],
            'future_value': [],
            'endorsement_part': endorsement_part.id,
            'delete_future': False,
            'effective_date': endorsement_date,
            'endorsement_definition':
            self.select_endorsement.endorsement_definition.id,
            }
        if current:
            result['current_value'].append(current.id)
            result['new_value'] = [self.get_new_instance_fields(current,
                    endorsed_fields)]
        if future:
            result['future_value'].append(future.id)
        endorsements = self.get_endorsements_for_state(state_name)
        if endorsements:
            # TODO : multi contracts ?
            endorsement = endorsements[0]
            self.update_defaults_from_endorsement(result,
                endorsement, endorsed_field_name)
        result['new_value'][0]['date'] = endorsement_date
        return result


class OpenContractAtApplicationDate(Wizard):
    'Open Contract at Application Date'

    __name__ = 'endorsement.contract.open'

    start_state = 'open_'
    open_ = StateAction('endorsement.act_open_contract_at_date')

    @classmethod
    def __setup__(cls):
        super(OpenContractAtApplicationDate, cls).__setup__()
        cls._error_messages.update({
                'endorsement_not_applied': 'Endorsement is not yet applied',
                })

    def do_open_(self, action):
        Endorsement = Pool().get('endorsement')
        endorsement = Endorsement(Transaction().context.get('active_id'))
        if endorsement.state != 'applied':
            self.raise_user_error('endorsement_not_applied')
        action['pyson_context'] = PYSONEncoder().encode({
                'contracts': [x.contract.id
                    for x in endorsement.contract_endorsements],
                '_datetime': endorsement.contract_endorsements[0].applied_on,
                })
        return action, {}
