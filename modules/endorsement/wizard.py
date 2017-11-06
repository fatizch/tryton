# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import defaultdict
from operator import attrgetter
from dateutil.relativedelta import relativedelta

from trytond.pool import Pool, PoolMeta
from trytond.model import Model, fields as tryton_fields
from trytond.transaction import Transaction
from trytond.server_context import ServerContext
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.wizard import StateAction
from trytond.pyson import Eval, Bool, In, And, Not, Len, If, PYSONEncoder

from trytond.modules.coog_core import model, fields, utils, coog_date

OPTION_ACTIONS = [
    ('nothing', ''),
    ('terminated', 'Terminated'),
    ('void', 'Void'),
    ('modified', 'Modified'),
    ('added', 'Added'),
    ]

__metaclass__ = PoolMeta
__all__ = [
    'add_endorsement_step',
    'DummyStep',
    'RecalculateContract',
    'ReactivateContract',
    'SelectEndorsement',
    'BasicPreview',
    'StartEndorsement',
    'OpenContractAtApplicationDate',
    'ChangeContractStartDate',
    'ChangeContractExtraData',
    'ManageOptions',
    'OptionDisplayer',
    'TerminateContract',
    'VoidContract',
    'ChangeContractSubscriber',
    'ManageContacts',
    'ContactDisplayer',
    'EndorsementWizardStepMixin',
    'EndorsementWizardStepBasicObjectMixin',
    'EndorsementWizardStepVersionedObjectMixin',
    'EndorsementRecalculateMixin',
    'EndorsementWizardPreviewMixin',
    'EndorsementSelectDeclineReason',
    'EndorsementDecline',
    ]


def add_endorsement_step(wizard_class, step_class, step_name):
    '''
        This method adds a StateView named <step_name> on the class
        <wizard_class>. This state view will be bound to the model defined by
        <step_class>.

        It will automatically add previous, next, and suspend transitions.
        The methods defining those transistions will be automatically defined
        and bound to the matching method which will be defined on <step_class>.
        The default method for the state view will be defined as well.

            default             =>  step_default
            transition_next     =>  step_next
            transition_previous =>  step_previous
            transition_suspend  =>  step_suspend

        The default behaviour for those method is that of the
        EndorsementWizardStepMixin class definitions.
    '''
    def get_step_method(kind):
        def wizard_method(wizard, *args, **kwargs):
            cur_state = getattr(wizard, step_name, None)
            if not cur_state or isinstance(cur_state, StateView):
                cur_state = Pool().get(step_class.__name__)()
            cur_state._wizard = wizard
            cur_state._step_name = step_name
            return getattr(cur_state, 'step_' + kind)(*args, **kwargs)
        return wizard_method

    setattr(wizard_class, step_name, step_class._get_state_view(step_name))
    setattr(wizard_class, step_name + '_previous', StateTransition())
    setattr(wizard_class, step_name + '_next', StateTransition())
    setattr(wizard_class, step_name + '_suspend', StateTransition())
    setattr(wizard_class, 'default_' + step_name, get_step_method('default'))
    setattr(wizard_class, 'transition_' + step_name + '_previous',
        get_step_method('previous'))
    setattr(wizard_class, 'transition_' + step_name + '_next',
        get_step_method('next'))
    setattr(wizard_class, 'transition_' + step_name + '_suspend',
        get_step_method('suspend'))


class EndorsementWizardStepMixin(model.CoogView):
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
        return self.step_update()

    @classmethod
    def is_multi_instance(cls):
        return True

    @classmethod
    def get_methods_for_model(cls, model_name):
        pool = Pool()
        Contract = pool.get('contract')
        methods = set()
        if model_name == 'contract':
            methods = methods | Contract._calculate_methods_after_endorsement()
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        return set()

    @property
    def step_name(self):
        return self._step_name

    @property
    def wizard(self):
        return self._wizard

    @classmethod
    def state_view_name(cls):
        raise NotImplementedError

    @classmethod
    def _get_state_view(cls, step_name):
        return StateView(cls.__name__, cls.state_view_name(), [
                Button('Previous', step_name + '_previous',
                    'tryton-go-previous'),
                Button('Cancel', 'end', 'tryton-cancel'),
                Button('Suspend', step_name + '_suspend', 'tryton-save'),
                Button('Next', step_name + '_next', 'tryton-go-next',
                    default=True)])

    def step_default(self, name=None):
        self.endorsement_definition = self.wizard.definition
        self.endorsement_part = self.wizard.get_endorsement_part_for_state(
            self.step_name)
        self.effective_date = self.wizard.select_endorsement.effective_date
        return {
            'endorsement_definition': self.endorsement_definition.id,
            'endorsement_part': self.endorsement_part.id,
            'effective_date': self.effective_date,
            }

    def step_previous(self):
        self.wizard.end_current_part(self.step_name)
        return self.wizard.get_state_before(self.step_name)

    def step_suspend(self):
        self.step_update()
        return 'end'

    def step_next(self):
        self.wizard.end_current_part(self.step_name)
        return self.wizard.get_next_state(self.step_name)

    def step_update(self):
        raise NotImplementedError

    @classmethod
    def check_before_start(cls, select_screen):
        '''
            This methods will be called before the first step of the start
            endorsement wizard. Its purpose is to check the consistency of the
            basic data (contract / date / subscriber) regarding this particular
            endorsement state. The first parameter is the
            endorsement.start.select record from the wizard.
        '''
        error_manager = ServerContext().context.get('error_manager', None)
        pool = Pool()
        Endorsement = pool.get('endorsement')
        endorsement = select_screen.endorsement
        if endorsement:
            contracts = [x.contract
                for x in getattr(endorsement, 'contract_endorsements', [])]
        elif getattr(select_screen, 'contract', None):
            contracts = [select_screen.contract]
        else:
            contracts = []
        if (not error_manager or 'effective_date_before_start_date'
                not in [x[0] for x in error_manager._errors]):
            if (not cls.allow_effective_date_before_contract(select_screen) and
                    any([x.start_date > select_screen.effective_date
                            for x in contracts if x.start_date])):
                Endorsement.append_functional_error(
                    'effective_date_before_start_date')
        if (not error_manager or 'active_contract_required'
                not in [x[0] for x in error_manager._errors]):
            if (not cls.allow_inactive_contracts() and
                    any([x.status != 'active' for x in contracts])):
                Endorsement.append_functional_error('active_contract_required')

    @classmethod
    def must_skip_step(cls, data_dict):
        '''
            Override this method to automatically skip this step if some
            conditions are met.
            This check is performed once when starting the endorsement, with
            the data available in the endorsement selection screen, then
            everytime the step should be displayed.
        '''
        return False

    @classmethod
    def allow_effective_date_before_contract(cls, select_screen):
        return any(x.view == 'change_start_date'
            for x in select_screen.endorsement_definition.endorsement_parts)

    @classmethod
    def allow_inactive_contracts(cls):
        return False

    def _get_contracts(self):
        return {x.contract.id: x
            for x in self.wizard.endorsement.contract_endorsements}

    @classmethod
    def _update_values(cls, new_instance, base_instance, values, fnames):
        dict_modified = False
        for fname in fnames:
            destination = getattr(new_instance, fname)
            origin = getattr(base_instance, fname)
            if isinstance(destination, Model):
                destination = destination.id
            if isinstance(origin, Model):
                origin = origin.id
            if fname not in values:
                if origin != destination:
                    values[fname] = destination
                    dict_modified = True
            else:
                if origin == destination:
                    values.pop(fname)
                else:
                    values[fname] = destination
                dict_modified = True
        return dict_modified

    @classmethod
    def _get_default_values(cls, values, default, fnames):
        result = {}
        for fname in fnames:
            if fname == 'id':
                # Special treatment for id, the displayer cannot use the 'id'
                # field, so we use _id instead
                result['id_'] = default.id
                continue
            fval = values.get(fname, getattr(default, fname, None))
            fval = fval.id if isinstance(fval, Model) else fval
            if isinstance(fval, (list, tuple)):
                fval = [x.id for x in fval]
            result[fname] = fval
        return result

    @classmethod
    def _update_endorsement(cls, endorsement, data_dict):
        pool = Pool()
        Model = pool.get(
            pool.get(endorsement.__class__._fields['values'].schema_model)
            ._get_model())
        endorsement.clean()
        new_values = {}
        for k, v in data_dict.iteritems():
            if k in endorsement._auto_update_ignore_fields():
                continue
            field = Model._fields[k]
            if isinstance(field, tryton_fields.Function):
                if not field.setter:
                    continue
                field = field._field
            if k in ('create_date', 'create_uid', 'write_date', 'write_uid'):
                continue
            if isinstance(field, (tryton_fields.One2Many,
                        tryton_fields.Many2Many)):
                if isinstance(field, tryton_fields.One2Many):
                    target_model = field.model_name
                else:
                    target_model = pool.get(field.relation_name)._fields[
                        field.target].model_name
                new_name, new_field = endorsement._get_field_for_model(
                    target_model)
                EndorsedModel = pool.get(new_field.model_name)
                values = []
                for action_data in v:
                    if action_data[0] == 'delete':
                        for id_to_del in action_data[1]:
                            values.append(EndorsedModel(action='remove',
                                    relation=id_to_del))
                    elif action_data[0] == 'write':
                        for id_to_update in action_data[1]:
                            new_endorsed_data = EndorsedModel(action='update',
                                relation=id_to_update)
                            cls._update_endorsement(new_endorsed_data,
                                action_data[2])
                            values.append(new_endorsed_data)
                    elif action_data[0] == 'add':
                        for id_to_add in action_data[1]:
                            values.append(EndorsedModel(action='add',
                                    relation=id_to_add))
                    elif action_data[0] == 'create':
                        for data_dict in action_data[1]:
                            new_endorsed_data = EndorsedModel(action='add')
                            cls._update_endorsement(new_endorsed_data,
                                data_dict)
                            values.append(new_endorsed_data)
                    elif action_data[0] == 'remove' and isinstance(field,
                            tryton_fields.Many2Many):
                        for id_to_remove in action_data[1]:
                            values.append(EndorsedModel(action='remove',
                                    relation=id_to_del))
                    else:
                        raise Exception(
                            'unsupported operation on XXX2Many : %s' % str(
                                action_data))
                setattr(endorsement, new_name, values)
            elif isinstance(field, tryton_fields.Dict) and v:
                setattr(endorsement, endorsement._reversed_endorsed_dict[k], v)
            else:
                new_values[k] = v
        endorsement.values = new_values


class DummyStep(EndorsementWizardStepMixin):
    'Dummy Step'

    __name__ = 'endorsement.start.dummy_step'


class EndorsementRecalculateMixin(EndorsementWizardStepMixin):
    '''
        Used to easily create new steps to trigger method calls on endorsed
        objects. Only possible modification is the effective_date of the
        endorsement
    '''
    @classmethod
    def __setup__(cls):
        super(EndorsementRecalculateMixin, cls).__setup__()
        cls.effective_date.states['readonly'] = False

    def step_update(self):
        self.wizard.endorsement.effective_date = self.effective_date
        self.wizard.endorsement.save()

    @classmethod
    def get_methods_for_model(cls, model_name):
        return set()

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        return set()


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
            if endorsed_field.name not in endorsement.values:
                continue
            value[endorsed_field.name] = endorsement.values[
                endorsed_field.name]

    @classmethod
    def get_state_view_default_values(cls, wizard, endorsed_field_view,
            endorsed_model, state_name, endorsement_part_field):
        pool = Pool()
        View = pool.get('ir.ui.view')
        good_view, = View.search([('xml_id', '=', endorsed_field_view)])
        endorsed_fields = wizard.get_fields_to_get(endorsed_model,
            good_view.id)
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


class RecalculateContract(EndorsementRecalculateMixin):
    'Recalculate Contract after endorsement'

    __name__ = 'endorsement.contract.recalculate'

    @classmethod
    def state_view_name(cls):
        return 'endorsement.recalculate_contract_view_form'

    @classmethod
    def get_methods_for_model(cls, model_name):
        pool = Pool()
        Contract = pool.get('contract')
        methods = set()
        if model_name == 'contract':
            methods = methods | Contract._calculate_methods_after_endorsement()
        return methods


class ChangeContractStartDate(EndorsementWizardStepMixin):
    'Change contract start date'

    __name__ = 'endorsement.contract.change_start_date'

    current_start_date = fields.Date('Current Start Date', readonly=True)
    new_start_date = fields.Date('New Start Date', readonly=True)

    @classmethod
    def allow_effective_date_before_contract(cls, select_screen):
        return True

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(ChangeContractStartDate, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods.add('update_start_date')
        return methods

    @classmethod
    def is_multi_instance(cls):
        return False

    def update_endorsement(self, base_endorsement, wizard):
        base_endorsement.values = {
            'start_date': wizard.endorsement.effective_date}
        base_endorsement.save()

    @classmethod
    def update_default_values(cls, wizard, base_endorsement, default_values):
        return {
            'new_start_date': wizard.endorsement.effective_date,
            }


class ReactivateContract(EndorsementWizardStepMixin):
    'Reactivate Contract'

    __name__ = 'endorsement.contract.reactivate'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    current_end_date = fields.Date('Current End Date', readonly=True)
    end_motive = fields.Many2One('contract.sub_status', 'End Motive',
        readonly=True)

    @classmethod
    def state_view_name(cls):
        return 'endorsement.endorsement_reactivate_contract_view_form'

    @classmethod
    def is_multi_instance(cls):
        return False

    @classmethod
    def allow_inactive_contracts(cls):
        return True

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = set()
        if model_name == 'contract':
            methods.add('reactivate_through_endorsement')
        return methods

    def step_default(self, name):
        pool = Pool()
        Contract = pool.get('contract')
        contracts = self._get_contracts()
        assert contracts
        for contract_id, endorsement in contracts.iteritems():
            contract = Contract(contract_id)
            if contract.status != 'hold':
                self.wizard.endorsement.effective_date = contract.end_date
                self.wizard.endorsement.save()
                break
        defaults = super(ReactivateContract, self).step_default()
        defaults['current_end_date'] = contract.end_date
        defaults['end_motive'] = (contract.sub_status.id if contract.sub_status
            else None)
        defaults['contract'] = contract.id
        return defaults

    def step_update(self):
        # No input data, everything will be handled in the endorsement methods
        pass


class ChangeContractExtraData(EndorsementWizardStepMixin):
    'Change contract extra data'

    __name__ = 'endorsement.contract.change_extra_data'

    current_extra_data_date = fields.Date('Date of Current Extra Data')
    current_extra_data = fields.Dict(
        'extra_data', 'Current Extra Data')
    new_extra_data_date = fields.Date('Date of New Extra Data')
    new_extra_data = fields.Dict(
        'extra_data', 'New Extra Data')

    @classmethod
    def is_multi_instance(cls):
        return False

    def step_default(self, name):
        pool = Pool()
        Contract = pool.get('contract')
        defaults = super(ChangeContractExtraData, self).step_default()
        contracts = self._get_contracts()
        for contract_id, endorsement in contracts.iteritems():
            contract = Contract(contract_id)
            effective_date = self.wizard.endorsement.effective_date
            extra_data_at_date = utils.get_value_at_date(contract.extra_datas,
                effective_date)
            extra_data_values = extra_data_at_date.extra_data_values
            defaults['current_extra_data_date'] = extra_data_at_date.date
            defaults['new_extra_data_date'] = effective_date if \
                effective_date != contract.start_date else None
            defaults['current_extra_data'] = extra_data_values

            if endorsement.extra_datas:
                data_values = \
                    endorsement.extra_datas[-1].new_extra_data_values \
                    or endorsement.extra_datas[-1].values['extra_data_values']
                defaults['new_extra_data'] = data_values
            else:
                defaults['new_extra_data'] = extra_data_values

        return defaults

    def step_update(self):
        pool = Pool()
        EndorsementExtraData = pool.get(
            'endorsement.contract.extra_data')
        Contract = pool.get('contract')
        contracts = self._get_contracts()

        for contract_id, endorsement in contracts.iteritems():
            EndorsementExtraData.delete(endorsement.extra_datas)
            contract = Contract(contract_id)

            if self.new_extra_data == self.current_extra_data:
                continue
            elif self.effective_date == self.current_extra_data_date \
                    or self.effective_date == contract.start_date:
                extra_data_at_date = utils.get_value_at_date(
                    contract.extra_datas, self.effective_date)
                extra_data_endorsement = EndorsementExtraData(
                    action='update',
                    contract_endorsement=endorsement,
                    extra_data=extra_data_at_date,
                    relation=extra_data_at_date.id,
                    definition=self.endorsement_definition,
                    new_extra_data_values=self.new_extra_data,
                    )
            else:
                extra_data_endorsement = EndorsementExtraData(
                    action='add',
                    contract_endorsement=endorsement,
                    definition=self.endorsement_definition,
                    values={'date': self.new_extra_data_date},
                    new_extra_data_values=self.new_extra_data,
                    )
            extra_data_endorsement.save()
            endorsement.save()

    @classmethod
    def state_view_name(cls):
        return 'endorsement.endorsement_change_contract_extra_data_view_form'


class ManageOptions(EndorsementWizardStepMixin):
    'Manage Options'
    '''
        This endorsement step allows to manage all options on a number of
        contracts. It stores all possible options, and only displays those
        relevant to the parent selected by the user :

          - possible_parents : The list of possible parents. They may be :
              > contract
              > endorsement.contract
              > anything else which has a list of options (e.g. covered_element
                in endorsement_insurance)

          - current_parent : The currently selected parent. The possible values
            are calculated from the possible_parents field.

          - current_options : The options (including modifications) related to
            the currently selected parent.

          - all_options : All possible options (including modifications) for
            all possible parents. This is a way to store all data in the view
            and just filter it by parent to get current_options.

          - new_coverage : The coverage for which an option will be created
            when the user clicks on the 'New Option' button

          - possible_coverages : The possible coverages that may be added to
            the current parent options. This list depends on the parent
            (obviously), and on the current options (cannot subscriber an
            already subscribed option at the endorsement effective date). It
            also makes sure that coverage exclusions are satisfied.
    '''

    __name__ = 'contract.manage_options'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    current_parent = fields.Selection('get_possible_parents',
        'Parent')
    all_options = fields.One2Many('contract.manage_options.option_displayer',
        None, 'All Options')
    current_options = fields.One2Many(
        'contract.manage_options.option_displayer', None, 'Current Options')
    new_coverage = fields.Many2One('offered.option.description',
        'New Coverage', domain=[('id', 'in', Eval('possible_coverages'))],
        states={'invisible': ~Eval('possible_coverages')},
        depends=['possible_coverages'])
    possible_coverages = fields.Many2Many('offered.option.description', None,
        None, 'Possible Coverages')
    possible_parents = fields.Text('Possible Parents', readonly=True)

    @classmethod
    def __setup__(cls):
        super(ManageOptions, cls).__setup__()
        cls._buttons.update({'add_option': {
                    'readonly': ~Eval('new_coverage'),
                    'invisible': ~Eval('possible_coverages'),
                    }})

    @classmethod
    def view_attributes(cls):
        return super(ManageOptions, cls).view_attributes() + [(
                '/form/group[@id="invisible"]',
                'states',
                {'invisible': True})]

    @property
    def _parent(self):
        if not getattr(self, 'current_parent', None):
            return None
        parent_model, parent_id = self.current_parent.split(',')
        return Pool().get(parent_model)(int(parent_id))

    @fields.depends('possible_parents')
    def get_possible_parents(self):
        if not self.possible_parents:
            return []
        return [tuple(x.split('|', 1))
            for x in self.possible_parents.split('\n')]

    @fields.depends('all_options', 'contract', 'current_options',
        'current_parent', 'effective_date', 'new_coverage',
        'possible_coverages')
    def on_change_current_parent(self):
        self.update_contract()
        if self.contract is None:
            return
        self.update_all_options()
        self.update_current_options()
        self.update_possible_coverages()

    @fields.depends('current_options', 'current_parent', 'effective_date',
        'possible_coverages')
    def on_change_current_options(self):
        if not self.current_parent:
            return
        self.update_possible_coverages()

    def calculate_possible_parents(self):
        return list(self.wizard.endorsement.contract_endorsements)

    def update_contract(self):
        if isinstance(self._parent, Pool().get('endorsement.contract')):
            self.contract = self._parent.contract
        elif self._parent is None:
            self.contract = None
        else:
            raise NotImplementedError

    def update_all_options(self):
        if not self.current_options:
            return
        new_options = list(self.current_options)
        for option in self.all_options:
            if option.parent == new_options[0].parent:
                continue
            new_options.append(option)
        self.all_options = new_options

    def update_current_options(self):
        new_options = []
        coverage_order = {x.coverage.id: idx
            for idx, x in enumerate(self.contract.product.ordered_coverages)}
        for option in sorted(self.all_options, key=lambda x: (x.parent,
                    coverage_order[x.coverage.id], x.start_date)):
            if option.parent == self.current_parent:
                new_options.append(option)
        self.current_options = new_options

    def update_possible_coverages(self):
        self.new_coverage = None
        current_coverages = {
            x.coverage for x in self.current_options
            if x.action != 'void'
            and x.start_date <= self.effective_date
            and (not x.end_date or x.end_date >= self.effective_date)}
        exclusions = set(sum([
                    list(x.options_excluded) for x in current_coverages], []))
        self.possible_coverages = list(
            self.get_all_possible_coverages(self._parent) - current_coverages
            - exclusions)
        if len(self.possible_coverages) == 1:
            self.new_coverage = self.possible_coverages[0]

    def step_default(self, field_names):
        defaults = super(ManageOptions, self).step_default()
        possible_parents = self.calculate_possible_parents()
        possible_parents = self.filtered_parents(possible_parents)
        defaults['possible_parents'] = '\n'.join(
            [str(x) + '|' + self.get_parent_name(x) for x in possible_parents])
        per_parent = {x: self.get_options_from_parent(x)
            for x in possible_parents}

        all_options = []
        for possible_parent, per_coverage in per_parent.iteritems():
            all_options += self.generate_displayers(possible_parent,
                per_coverage)
        defaults['all_options'] = [x._changed_values for x in all_options]
        if defaults['all_options']:
            defaults['current_parent'] = defaults['all_options'][0]['parent']
        return defaults

    @classmethod
    def filtered_parents(cls, possible_parents):
        return [x for x in possible_parents if
            cls.get_all_possible_coverages(x)]

    def step_update(self):
        self.update_all_options()
        endorsement = self.wizard.endorsement
        per_parent = defaultdict(list)
        for option in self.all_options:
            per_parent[option.parent].append(option)

        contract_endorsements = {}
        for contract_endorsement in endorsement.contract_endorsements:
            contract = contract_endorsement.contract
            utils.apply_dict(contract, contract_endorsement.apply_values())
            contract_endorsements[contract.id] = contract

        for parent, new_options in per_parent.iteritems():
            self.current_parent = parent
            parent = self.get_parent_endorsed(self._parent,
                contract_endorsements)
            parent.options = getattr(parent, 'options', [])
            existing_options = defaultdict(list)
            for option in parent.options:
                existing_options[option.coverage].append(option)
            self.update_endorsed_options(new_options, parent, existing_options)
            parent.options = list(parent.options)

        new_endorsements = []
        for contract_endorsement in endorsement.contract_endorsements:
            self._update_endorsement(contract_endorsement,
                contract_endorsement.contract._save_values)
            if not contract_endorsement.clean_up():
                new_endorsements.append(contract_endorsement)
        endorsement.contract_endorsements = new_endorsements
        endorsement.save()

    def get_parent_endorsed(self, parent, contract_endorsements):
        if isinstance(parent, Pool().get('endorsement.contract')):
            return contract_endorsements[parent.contract.id]
        else:
            raise NotImplementedError

    def update_endorsed_options(self, new_options, parent, existing_options):
        per_id = {x.id: x for x in parent.options}
        for new_option in new_options:
            if new_option.action == 'nothing':
                self._update_nothing(new_option, parent, existing_options,
                    per_id)
                continue
            if new_option.action == 'void':
                assert new_option.cur_option_id
                self._update_void(new_option, parent, existing_options,
                    per_id)
                continue
            if new_option.action == 'terminated':
                self._update_terminated(new_option, parent, existing_options,
                    per_id)
                continue
            if new_option.action == 'added':
                self._update_added(new_option, parent, existing_options,
                    per_id)
                continue
            if new_option.action == 'modified':
                self._update_modified(new_option, parent, existing_options,
                    per_id)
                continue
        # Remove deleted options
        to_remove = []
        for coverage in set(existing_options.keys()) - {x.coverage
                for x in new_options}:
            to_remove += [x for x in existing_options[coverage]
                if getattr(x, 'id', 0) <= 0]
        parent.options = [x for x in parent.options if x not in to_remove]

    def _update_nothing(self, new_option, parent, existing_options, per_id):
        # Cancel modifications
        assert new_option.cur_option_id
        Option = Pool().get('contract.option')
        prev_option = Option(new_option.cur_option_id)
        option = per_id[new_option.cur_option_id]
        option.versions = prev_option.versions
        option.manual_end_date = prev_option.manual_end_date
        option.status = prev_option.status
        option.sub_status = prev_option.sub_status

    def _update_void(self, new_option, parent, existing_options, per_id):
        assert new_option.cur_option_id
        existing_option = per_id[new_option.cur_option_id]
        existing_option.status = new_option.action
        existing_option.sub_status = new_option.sub_status

    def _update_terminated(self, new_option, parent, existing_options, per_id):
        assert new_option.cur_option_id
        existing_option = per_id[new_option.cur_option_id]
        existing_option.status = new_option.action
        existing_option.sub_status = new_option.sub_status
        existing_option.manual_end_date = new_option.end_date

    def _update_added(self, new_option, parent, existing_options, per_id):
        for option in existing_options[new_option.coverage]:
            if getattr(option, 'manual_start_date', None) != \
                    self.effective_date:
                continue
            # New option => only update
            option.versions = [new_option.to_version()]
            break
        else:
            option = new_option.to_option()
        parent.options = [x for x in parent.options
            if x.coverage != new_option.coverage
            or getattr(x, 'manual_start_date', None) != self.effective_date
            ] + [option]

    def _update_modified(self, new_option, parent, existing_options, per_id):
        assert new_option.cur_option_id
        good_option = per_id[new_option.cur_option_id]
        new_versions = sorted([v for v in good_option.versions
                if not v.start or v.start <= new_option.effective_date],
            key=lambda x: x.start or datetime.date.min)
        current_version = new_versions[-1]
        if current_version.start_date == new_option.effective_date:
            current_version.extra_data = new_option.extra_data
        elif not current_version.start or (current_version.start !=
                new_option.effective_date):
            current_version = new_option.to_version(
                previous_version=new_versions[-1])
            new_versions.append(current_version)
        good_option.versions = new_versions

    def get_options_from_parent(self, parent):
        if isinstance(parent, Pool().get('endorsement.contract')):
            contract = parent.contract
            utils.apply_dict(contract, parent.apply_values())
            return self.contract_options_per_coverage(contract)
        else:
            raise NotImplementedError

    def copy_option_data(self, previous_option, new_option):
        pass

    def contract_options_per_coverage(self, contract):
        per_coverage = defaultdict(list)
        for option in contract.options:
            per_coverage[option.coverage].append(option)
        return per_coverage

    def generate_displayers(self, parent, per_coverage):
        Displayer = Pool().get('contract.manage_options.option_displayer')
        all_options = []
        for options in per_coverage.itervalues():
            for idx, option in enumerate(sorted(options,
                        key=lambda x: x.manual_start_date or x.start_date)):
                save_values = option._values
                if not save_values and (self.effective_date > (
                            getattr(option, 'manual_end_date',
                                getattr(option, 'end_date', None))
                            or datetime.date.max)
                        or getattr(option, 'status', '') == 'void'):
                    continue
                displayer = Displayer.new_displayer(option,
                    self.effective_date)
                displayer.parent = str(parent)
                displayer.parent_rec_name = self.get_parent_name(parent)
                all_options.append(displayer)
                if not save_values:
                    # Not modified option
                    displayer.action = 'nothing'
                    continue
                if option.id:
                    # Option existed before, either modification or resiliation
                    if (option.get_version_at_date(self.effective_date).start
                            == self.effective_date):
                        displayer.action = 'modified'
                    else:
                        # Only option, resiliation
                        displayer.action = option.status
                    break
                # New option
                displayer.action = 'added'
                displayer.update_icon()
        return all_options

    def get_parent_name(self, parent):
        if isinstance(parent, Pool().get('endorsement.contract')):
            return parent.contract.rec_name
        else:
            return parent.rec_name

    @classmethod
    def get_all_possible_coverages(cls, parent):
        if isinstance(parent, Pool().get('endorsement.contract')):
            return set(parent.contract.product.coverages)
        else:
            raise NotImplementedError

    @classmethod
    def state_view_name(cls):
        return 'endorsement.contract_manage_options_view_form'

    @model.CoogView.button_change('contract', 'current_options',
        'current_parent', 'effective_date', 'new_coverage',
        'possible_coverages')
    def add_option(self):
        assert self.new_coverage
        new_option = self.new_option()
        self.new_coverage = None
        self.current_options = list(self.current_options) + [new_option]
        self.update_possible_coverages()

    def new_option(self):
        new_option = Pool().get('contract.manage_options.option_displayer')()
        new_option.coverage_id = self.new_coverage.id
        new_option.action = 'added'
        new_option.update_icon()
        new_option.parent = self.current_parent
        new_option.parent_rec_name = self.get_parent_name(self._parent)
        new_option.start_date = self.effective_date
        new_option.effective_date = self.effective_date
        new_option.display_name = self.new_coverage.rec_name
        new_option.end_date = None
        new_option.sub_status = None
        new_option.extra_data = self.get_default_extra_data(self.new_coverage)
        new_option.update_extra_data_string()
        return new_option

    def get_default_extra_data(self, coverage):
        return self.contract.product.get_extra_data_def('option', {},
            self.effective_date, coverage=coverage)


class OptionDisplayer(model.CoogView):
    'Option Displayer'

    __name__ = 'contract.manage_options.option_displayer'

    action = fields.Selection(OPTION_ACTIONS, 'Action',
        domain=[If(Eval('action') == 'modified',
                ('action', 'in', ('modified', 'nothing')),
                If(Eval('action') == 'added',
                    ('action', '=', 'added'),
                    If(Eval('start_date') == Eval('effective_date'),
                        ('action', 'not in',
                            ('added', 'modified', 'terminated')),
                        ('action', 'not in', ('added', 'modified')))))],
        depends=['action', 'effective_date', 'start_date'])
    coverage_id = fields.Integer('Coverage Id', readonly=True)
    parent = fields.Char('Parent Reference', readonly=True)
    parent_rec_name = fields.Char('Parent', readonly=True)
    start_date = fields.Date('Start Date', readonly=True, required=True)
    end_date = fields.Date('End Date', states={
            'readonly': Eval('action') != 'added'},
        domain=[If(Eval('action') == 'added',
                [('end_date', '<=', Eval('effective_date'))],
                [])], depends=['action', 'effective_date'])
    extra_data = fields.Dict('extra_data', 'Extra Data', states={
            'invisible': ~Eval('extra_data')})
    extra_data_as_string = fields.Text('Extra Data', readonly=True, states={
            'invisible': ~Eval('extra_data')})
    display_name = fields.Char('Name', readonly=True)
    cur_option_id = fields.Integer('Existing Option', readonly=True)
    effective_date = fields.Date('Effective Date', readonly=True)
    sub_status = fields.Many2One('contract.sub_status', 'Sub Status',
        states={
            'required': In(Eval('action'), ['terminated', 'void']),
            'readonly': Not(In(Eval('action'), ['terminated', 'void'])),
            'invisible': Not(In(Eval('action'), ['terminated', 'void']))},
        domain=[If(In(Eval('action'), ['terminated', 'void']),
                [('status', '=', Eval('action'))],
                [])], depends=['action'])
    icon = fields.Char('Icon')

    @classmethod
    def __setup__(cls):
        super(OptionDisplayer, cls).__setup__()
        cls._error_messages.update({
                'new_option': 'New Option (%s)',
                })

    @property
    def _parent(self):
        if hasattr(self, '__parent'):
            return self.__parent
        if not getattr(self, 'parent', None):
            self.__parent = None
            return None
        parent_model, parent_id = self.parent.split(',')
        self.__parent = Pool().get(parent_model)(int(parent_id))
        return self.__parent

    @property
    def coverage(self):
        return Pool().get('offered.option.description')(self.coverage_id)

    @property
    def product(self):
        if not self._parent:
            return None
        if self._parent.__name__ == 'contract':
            return self._parent.product

    @fields.depends('action', 'cur_option_id', 'effective_date', 'end_date',
        'extra_data', 'extra_data_as_string', 'sub_status')
    def on_change_action(self):
        if not self.action:
            return
        pool = Pool()
        if self.action not in ('modified', 'added'):
            self.extra_data = pool.get('contract.option')(
                self.cur_option_id).get_version_at_date(
                self.effective_date).extra_data
            self.update_extra_data_string()

        if self.action == 'terminated':
            self.end_date = coog_date.add_day(self.effective_date, -1)
        else:
            if self.end_date == coog_date.add_day(self.effective_date, -1):
                if self.cur_option_id:
                    self.end_date = pool.get('contract.option')(
                        self.cur_option_id).end_date

    def update_icon(self):
        self.icon = ''
        if self.action == 'terminated':
            self.icon = 'stop'
        elif self.action == 'added':
            self.icon = 'plus'
        elif self.action == 'void':
            self.icon = 'void'
        elif self.action == 'modified':
            self.icon = 'shuffle'

    @fields.depends('action', 'cur_option_id', 'effective_date', 'extra_data',
        'extra_data_as_string', 'parent', 'coverage_id')
    def on_change_extra_data(self):
        if not self.extra_data and self.action is None:
            self.extra_data_as_string = ''
            return
        self.refresh_extra_data()
        self.update_extra_data_string()
        if self.action == 'added':
            return
        previous_extra_data = Pool().get('contract.option')(
            self.cur_option_id).get_version_at_date(
            self.effective_date).extra_data
        if self.extra_data != previous_extra_data and self.action == 'nothing':
            self.action = 'modified'
        elif self.extra_data == previous_extra_data and (
                self.action == 'modified'):
            self.action = 'nothing'
        self.update_icon()

    def refresh_extra_data(self):
        if not self.product:
            return
        self.extra_data = self.product.get_extra_data_def('option',
            self.extra_data, self.effective_date, coverage=self.coverage)

    def update_extra_data_string(self):
        self.extra_data_as_string = Pool().get(
            'extra_data').get_extra_data_summary([self], 'extra_data')[self.id]

    @classmethod
    def new_displayer(cls, option, effective_date):
        displayer = cls()
        displayer.effective_date = effective_date
        displayer.coverage_id = option.coverage.id
        if getattr(option, 'id', None):
            displayer.cur_option_id = option.id
            displayer.display_name = option.rec_name
        else:
            displayer.display_name = cls.raise_user_error('new_option', (
                    option.coverage.rec_name,), raise_exception=False)
        if getattr(option, 'versions', None) is None:
            option.versions = [Pool().get(
                    'contract.option.version').get_default_version()]
        displayer.start_date = option.manual_start_date or option.start_date
        displayer.end_date = getattr(option, 'manual_end_date', None)
        if displayer.end_date is None:
            displayer.end_date = getattr(option, 'end_date', None)
        displayer.sub_status = getattr(option, 'sub_status', None)
        displayer.action = 'nothing'
        displayer.extra_data = option.get_version_at_date(
            effective_date).extra_data
        return displayer

    def to_option(self):
        pool = Pool()
        Option = pool.get('contract.option')
        Version = pool.get('contract.option.version')
        option = Option(status='active', coverage=self.coverage)
        option.versions = [Version(**Version.get_default_version())]
        option.manual_start_date = self.effective_date
        option.start_date = self.effective_date
        option.get_version_at_date(self.effective_date).extra_data = \
            self.extra_data
        option.versions = list(option.versions)
        return option

    def to_version(self, previous_version=None):
        Version = Pool().get('contract.option.version')
        if previous_version is None:
            version = Version(start=None)
        else:
            version = Version(**model.dictionarize(previous_version,
                    self._option_fields_to_extract()))
            version.start = self.effective_date
        version.extra_data = self.extra_data
        return version

    def update_from_new_option(self, new_option):
        self.extra_data = getattr(new_option, 'extra_data', {})

    @classmethod
    def _option_fields_to_extract(cls):
        return {
            'contract.option': ['coverage', 'sub_status'],
            'contract.option.version': ['extra_data'],
            }


class TerminateContract(EndorsementWizardStepMixin):
    'Terminate Contract'

    __name__ = 'endorsement.contract.terminate'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    current_end_date = fields.Date('Current End Date', readonly=True)
    termination_date = fields.Date('Termination Date', required=True,
        readonly=True)
    termination_reason = fields.Many2One('contract.sub_status',
        'Termination Reason', required=True,
        domain=[('status', '=', 'terminated')])

    @classmethod
    def __setup__(cls):
        super(TerminateContract, cls).__setup__()
        cls._error_messages.update({
                'termination_date_must_be_anterior': 'The termination date '
                'must be anterior to the end date of the modified period: %s',
                'termination_date_must_be_posterior': 'The termination date '
                'must be posterior to the contract start date: %s',
                'termination_before_active_start_date': 'You are trying to '
                'terminate the contract before its active start date'
                })

    @classmethod
    def is_multi_instance(cls):
        return False

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(TerminateContract, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods -= {'calculate_activation_dates'}
            methods.add('plan_termination_or_terminate')
        return methods

    def endorsement_values(self):
        return {'termination_reason': self.termination_reason.id}

    @classmethod
    def check_before_start(cls, select_screen):
        super(TerminateContract, cls).check_before_start(select_screen)
        contracts = []
        endorsement = select_screen.endorsement
        if endorsement:
            contracts = [x.contract
                for x in getattr(endorsement, 'contract_endorsements', [])]
        elif hasattr(select_screen, 'contract'):
            contracts = [select_screen.contract]
        to_warn = []
        for contract in contracts:
            if select_screen.effective_date < contract.start_date:
                to_warn.append(str(contract.id))
        if to_warn:
            warning_id = ','.join(to_warn[0:10])
            cls.raise_user_warning(
                'termination_before_active_start_date_%s' % warning_id,
                'termination_before_active_start_date')

    @classmethod
    def allow_effective_date_before_contract(cls, select_screen):
        endorsement = select_screen.endorsement
        contracts = []
        if endorsement:
            contracts = [c.contract for c in endorsement.contract_endorsements]
        elif hasattr(endorsement, 'contract'):
            contracts = [select_screen.contract]
        return all([x.initial_start_date <= select_screen.effective_date
                for x in contracts])

    def step_default(self, name):
        pool = Pool()
        Contract = pool.get('contract')
        defaults = super(TerminateContract, self).step_default()
        contracts = self._get_contracts()
        for contract_id, endorsement in contracts.iteritems():
            if endorsement.values and 'end_date' in endorsement.values:
                defaults['termination_date'] = endorsement.values['end_date']
            else:
                defaults['termination_date'] = \
                    self.wizard.endorsement.effective_date
            defaults['contract'] = contract_id
            defaults['current_end_date'] = Contract(contract_id).end_date
        return defaults

    def step_update(self):
        pool = Pool()
        Date = pool.get('ir.date')
        lang = pool.get('res.user')(Transaction().user).language
        EndorsementActivationHistory = pool.get(
            'endorsement.contract.activation_history')
        ActivationHistory = pool.get('contract.activation_history')
        Contract = pool.get('contract')
        contract_id, endorsement = self._get_contracts().items()[0]

        contract = Contract(contract_id)
        last_period = contract.activation_history[-1]
        endorsement.values = {'end_date': self.termination_date}

        if self.termination_date < contract.initial_start_date:
            self.raise_user_error('termination_date_must_be_posterior',
                Date.date_as_string(contract.start_date, lang))

        # first case : we are terminating a contract after its current
        # term
        if self.termination_date > (contract.end_date or datetime.date.max):
            if last_period.end_date == contract.end_date or \
                    self.termination_date > last_period.end_date:
                self.raise_user_error('termination_date_must_be_anterior',
                    Date.date_as_string(last_period.end_date, lang))
            endorsement.activation_history = [EndorsementActivationHistory(
                    action='update',
                    contract_endorsement=endorsement,
                    activation_history=last_period,
                    definition=self.endorsement_definition,
                    values=self.endorsement_values())]
        # second case : we are terminating a contract during its current
        # term
        else:
            # No next period
            if contract.end_date == last_period.end_date:
                if self.termination_date < last_period.start_date:
                    history_endorsements = []
                    valid_activation_history = []
                    for activation_history in contract.activation_history:
                        if (activation_history.start_date >
                                self.termination_date):
                            history_endorsements.append(
                                EndorsementActivationHistory(
                                    action='remove',
                                    contract_endorsement=endorsement,
                                    activation_history=activation_history))
                        else:
                            valid_activation_history.append(activation_history)
                    latest = max(valid_activation_history,
                        key=attrgetter('start_date'))
                    history_endorsements.append(EndorsementActivationHistory(
                            action='update',
                            contract_endorsement=endorsement,
                            activation_history=latest,
                            values=self.endorsement_values()))
                    endorsement.activation_history = history_endorsements
                # remove activation_history
                else:
                    endorsement.activation_history = [
                        EndorsementActivationHistory(
                            action='update',
                            contract_endorsement=endorsement,
                            activation_history=last_period,
                            definition=self.endorsement_definition,
                            values=self.endorsement_values())]
            # We have a next period, we must remove it,
            # And update the current term period
            else:
                if self.termination_date > last_period.end_date:
                    self.raise_user_error(
                        'termination_date_must_be_anterior',
                        Date.date_as_string(last_period.end_date, lang))
                history_endorsements = []
                history_endorsements.append(EndorsementActivationHistory(
                        action='remove',
                        contract_endorsement=endorsement,
                        activation_history=last_period,
                        definition=self.endorsement_definition))

                current_activation_history, = ActivationHistory.search([
                        ('contract', '=', contract),
                        ('end_date', '=', contract.end_date)])

                history_endorsements.append(EndorsementActivationHistory(
                        action='update',
                        contract_endorsement=endorsement,
                        activation_history=current_activation_history,
                        definition=self.endorsement_definition,
                        values=self.endorsement_values()))
                endorsement.activation_history = history_endorsements
            endorsement.save()

    @classmethod
    def state_view_name(cls):
        return 'endorsement.endorsement_terminate_contract_view_form'


class VoidContract(EndorsementWizardStepMixin):
    'Void Contract'

    __name__ = 'endorsement.contract.void'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    void_reason = fields.Many2One('contract.sub_status', 'Void Reason',
        required=True, domain=[('status', '=', 'void')])
    current_end_date = fields.Date('Current End Date', readonly=True)

    @classmethod
    def __setup__(cls):
        super(VoidContract, cls).__setup__()
        cls._error_messages.update({
                'void_renewed_contract': 'You are trying to void a renewed '
                'contract',
                })

    @classmethod
    def is_multi_instance(cls):
        return False

    def step_default(self, name):
        pool = Pool()
        Contract = pool.get('contract')
        defaults = super(VoidContract, self).step_default()
        contracts = self._get_contracts()
        for contract_id, endorsement in contracts.iteritems():
            defaults['contract'] = contract_id
            defaults['current_end_date'] = Contract(contract_id).end_date
        return defaults

    def step_update(self):
        pool = Pool()
        EndorsementActivationHistory = pool.get(
            'endorsement.contract.activation_history')
        EndorsementOption = pool.get('endorsement.contract.option')
        Contract = pool.get('contract')
        contract_id, endorsement = self._get_contracts().items()[0]

        contract = Contract(contract_id)
        endorsement.values = {'status': 'void', 'sub_status':
            self.void_reason.id}
        endorsement.activation_history = [EndorsementActivationHistory(
                action='update',
                contract_endorsement=endorsement,
                activation_history=activation_history,
                relation=activation_history.id,
                values={'active': False},
                definition=self.endorsement_definition)
            for activation_history in contract.activation_history]
        endorsement.options = [EndorsementOption(action='update',
                contract_endorsement=endorsement, relation=option.id,
                values={'status': 'void', 'sub_status': self.void_reason.id},
                definition=self.endorsement_definition)
            for option in contract.options]
        endorsement.save()

    @classmethod
    def state_view_name(cls):
        return 'endorsement.endorsement_void_contract_view_form'

    @classmethod
    def check_before_start(cls, select_screen):
        super(VoidContract, cls).check_before_start(select_screen)
        contracts = []
        endorsement = select_screen.endorsement
        if endorsement:
            contracts = [x.contract
                for x in getattr(endorsement, 'contract_endorsements', [])]
        elif hasattr(select_screen, 'contract'):
            contracts = [select_screen.contract]
        to_warn = []
        for contract in contracts:
            if select_screen.effective_date < contract.start_date:
                to_warn.append(str(contract.id))
        if to_warn:
            cls.raise_user_warning(
                'void_renewed_contract', 'void_renewed_contract')

    @classmethod
    def allow_effective_date_before_contract(cls, select_screen):
        endorsement = select_screen.endorsement
        contracts = []
        if endorsement:
            contracts = [c.contract for c in endorsement.contract_endorsements]
        elif hasattr(endorsement, 'contract'):
            contracts = [select_screen.contract]
        return all([x.initial_start_date <= select_screen.effective_date
                for x in contracts])


class ChangeContractSubscriber(EndorsementWizardStepMixin):
    'Change Contract Subscriber'

    __name__ = 'endorsement.contract.subscriber_change'

    current_subscriber = fields.Many2One('party.party', 'Current Subscriber',
        readonly=True)
    new_subscriber = fields.Many2One('party.party', 'New Subscriber',
        domain=[If(Bool(Eval('all_parties')),
                [],
                [('id', 'in', Eval('possible_subscribers'))])],
        depends=['all_parties', 'possible_subscribers'], required=True)
    possible_subscribers = fields.One2Many('party.party', None,
        'Possible Subscribers')
    all_parties = fields.Boolean('Display All Parties')

    def step_default(self, name):
        defaults = super(ChangeContractSubscriber, self).step_default()
        contracts = self._get_contracts()
        for contract_id, endorsement in contracts.iteritems():
            defaults['current_subscriber'] = \
                endorsement.contract.subscriber.id
            defaults['new_subscriber'] = endorsement.values.get('subscriber',
                None)
        return defaults

    def update_subscriber_contact_to_values(self, endorsement):
        pool = Pool()
        EndorsementContact = pool.get('endorsement.contract.contact')
        ContactType = pool.get('contract.contact.type')
        type_, = ContactType.search([('code', '=', 'subscriber')])
        subscriber_contacts = [c for c in endorsement.contract.contacts if
            c.type.code == 'subscriber']
        effective_date = endorsement.endorsement.effective_date
        new_contacts = []
        # max end date is the last end_date of subscriber contact
        max_end_date = datetime.date.min
        for contact in subscriber_contacts:
            if (contact.party == self.current_subscriber and (
                    not contact.end_date or
                    contact.end_date >= effective_date)):
                # if last subscriber contact is the right subscriber
                # update the end_date
                new_contacts.append(EndorsementContact(
                        action='update',
                        contract_endorsement=endorsement,
                        definition=self.endorsement_definition,
                        relation=contact.id,
                        contact=contact,
                        values={
                            'end_date': effective_date - relativedelta(days=1)
                            }))
                max_end_date = effective_date - relativedelta(days=1)
            elif max_end_date <= contact.end_date:
                max_end_date = contact.end_date
        # create a contact if not contact already exist for the old subscriber
        if max_end_date < effective_date - relativedelta(days=1):
            max_end_date = max_end_date - relativedelta(days=1) \
                if max_end_date != datetime.date.min else None
            new_contacts.append(EndorsementContact(
                    action='add',
                    contract_endorsement=endorsement,
                    definition=self.endorsement_definition,
                    values={
                        'date': max_end_date,
                        'end_date': effective_date - relativedelta(days=1),
                        'party': self.current_subscriber.id,
                        'type': type_.id,
                        'address': self.current_subscriber.
                        get_main_address_id()
                        }))
        endorsement.contacts = new_contacts

    def step_update(self):
        pool = Pool()
        EndorsementContract = pool.get('endorsement.contract')
        to_save = []
        for contract_id, endorsement_contract in self._get_contracts().items():
            endorsement_contract.values = {
                'subscriber': self.new_subscriber.id}
            self.update_subscriber_contact_to_values(endorsement_contract)
            to_save.append(endorsement_contract)
        EndorsementContract.save(to_save)

    @fields.depends('current_subscriber')
    def on_change_with_possible_subscribers(self, name=None):
        if not self.current_subscriber:
            return []
        return [r.to.id for r in self.current_subscriber.relations]

    @classmethod
    def state_view_name(cls):
        return 'endorsement.endorsement_change_contract_subscriber_view_form'


class ManageContacts(EndorsementWizardStepMixin, model.CoogView):
    'Manage Contacts'

    __name__ = 'endorsement.manage_contacts'

    contract = fields.Many2One('endorsement.contract', 'Contract',
        domain=[('id', 'in', Eval('possible_contracts', []))],
        states={'invisible': Len(Eval('possible_contracts', [])) == 1},
        depends=['possible_contracts'])
    possible_contracts = fields.Many2Many('endorsement.contract', None, None,
        'Possible Contracts')
    all_contacts = fields.One2Many('endorsement.manage_contacts.contact',
        None, 'All contacts')
    current_contacts = fields.One2Many(
        'endorsement.manage_contacts.contact', None, 'Current Contacts')

    @classmethod
    def view_attributes(cls):
        return super(ManageContacts, cls).view_attributes() + [(
                '/form/group[@id="invisible"]',
                'states',
                {'invisible': True})]

    @classmethod
    def state_view_name(cls):
        return 'endorsement.manage_contacts_view_form'

    @fields.depends('all_contacts', 'contract', 'current_contacts',
        'possible_contacts')
    def on_change_contract(self):
        self.update_all_contacts()
        self.update_current_contacts()

    @fields.depends('current_contacts', 'contract', 'effective_date')
    def on_change_current_contacts(self):
        for contact in self.current_contacts:
            if getattr(contact, 'action', None):
                continue
            contact.effective_date = self.effective_date
            contact.contract = self.contract
            contact.contract_rec_name = self.contract.contract.rec_name
            contact.action = 'added'
            self.current_contacts = list(self.current_contacts)
            return

    def update_all_contacts(self):
        if not self.current_contacts:
            return
        new_contacts = list(self.current_contacts)
        for contact in self.all_contacts:
            if contact.contract == new_contacts[0].contract:
                continue
            new_contacts.append(contact)
        self.all_contacts = new_contacts

    def update_current_contacts(self):
        new_contacts = []
        for contact in self.all_contacts:
            if contact.contract == self.contract:
                new_contacts.append(contact)
        self.current_contacts = new_contacts

    def step_default(self, field_names):
        defaults = super(ManageContacts, self).step_default()
        possible_contracts = self.wizard.endorsement.contract_endorsements

        if not possible_contracts and self.wizard.select_endorsement.contract:
            contract_endorsement = Pool().get('endorsement.contract')(
                contract=self.wizard.select_endorsement.contract,
                endorsement=self.wizard.endorsement)
            contract_endorsement.save()
            possible_contracts = [contract_endorsement]

        defaults['possible_contracts'] = [x.id for x in possible_contracts]
        per_contract = {x: self.get_updated_contacts_from_contract(x)
            for x in possible_contracts}

        all_contacts = []
        for contract, contacts in per_contract.iteritems():
            all_contacts += self.generate_displayers(contract, contacts)
        defaults['all_contacts'] = [x._changed_values for x in all_contacts]
        if defaults['possible_contracts']:
            defaults['contract'] = defaults['possible_contracts'][0]
        return defaults

    def step_update(self):
        self.update_all_contacts()
        endorsement = self.wizard.endorsement
        per_contract = defaultdict(list)
        for contact in self.all_contacts:
            per_contract[contact.contract].append(contact)

        for contract, contacts in per_contract.iteritems():
            self.update_endorsed_contacts(contract, contacts)

        new_endorsements = []
        for contract_endorsement in per_contract.keys():
            self._update_endorsement(contract_endorsement,
                contract_endorsement.contract._save_values)
            if not contract_endorsement.clean_up():
                new_endorsements.append(contract_endorsement)
        endorsement.contract_endorsements = new_endorsements
        endorsement.save()

    def update_endorsed_contacts(self, contract_endorsement, contacts):
        per_id = {x.id: x for x in contract_endorsement.contract.contacts}
        for contact in contacts:
            if contact.action == 'nothing':
                self._update_nothing(contract_endorsement.contract, contact,
                    per_id)
                continue
            if contact.action == 'ended':
                self._update_ended(contract_endorsement.contract, contact,
                    per_id)
                continue
            if contact.action == 'added':
                self._update_added(contract_endorsement.contract, contact,
                    per_id)
                continue
            if contact.action == 'new_address':
                self._update_modified(contract_endorsement.contract, contact,
                    per_id)
                continue
        contract_endorsement.contract.contacts = list(
            contract_endorsement.contract.contacts)

    def _update_nothing(self, contract, contact, per_id):
        # Cancel modifications
        if contact.automatic:
            return
        assert contact.contact_id
        Contact = Pool().get('contract.contact')
        prev_contact = Contact(contact.contact_id)
        contact = per_id[contact.contact_id]
        contact.address = prev_contact.address
        if contact.end_date != prev_contact.end_date:
            contact.end_date = prev_contact.end_date

    def _update_ended(self, contract, contact, per_id):
        if not contact.contact_id:
            return
        old_contact = per_id[contact.contact_id]
        old_contact.end_date = contact.end_date

    def _update_added(self, contract, contact, per_id):
        contract.contacts += (contact.to_contact(),)

    def _update_modified(self, contract, contact, per_id):
        if contact.contact_id:
            self._update_ended(contract, contact, per_id)
        contract.contacts += (contact.to_contact(),)

    def get_updated_contacts_from_contract(self, contract_endorsement):
        contract = contract_endorsement.contract
        contacts = {(x.type, x.party): [x, None]
            for x in self.get_contract_contacts(contract)}
        utils.apply_dict(contract, contract_endorsement.apply_values())

        for new_contact in self.get_contract_contacts(contract):
            key = (new_contact.type, new_contact.party)
            if key in contacts:
                contacts[key][1] = new_contact
            else:
                contacts[key] = [None, new_contact]
        return contacts

    def get_contract_contacts(self, contract):
        contacts = contract.get_contacts(date=self.effective_date,
            only_existing=True)
        for contact in contacts:
            if getattr(contact, 'type_code', None) is None:
                contact.type_code = contact.type.code if contact.type else ''
        if len([c for c in contacts if c.type_code == 'subscriber']) == 0:
            contacts += contract.get_contacts(date=self.effective_date,
                type_='subscriber')
        return contacts

    def generate_displayers(self, contract_endorsement, contacts):
        all_contacts = []
        for (kind, party), (old, new) in contacts.items():
            contact_displayer = self.new_contact_displayer(kind, party, old,
                new)
            contact_displayer.contract = contract_endorsement
            contact_displayer.contract_rec_name = \
                contract_endorsement.contract.rec_name
            contact_displayer.effective_date = self.effective_date
            all_contacts.append(contact_displayer)
        all_contacts.sort(key=lambda x: (x.contract, 0 if x.contact_id else 1,
                x.effective_date))
        return all_contacts

    def new_contact_displayer(self, kind, party, old, new):
        Contact = Pool().get('endorsement.manage_contacts.contact')
        new_contact = Contact()
        new_contact.kind = kind
        new_contact.type_code = kind.code if kind else ''
        new_contact.party = party
        new_contact.end_date = None
        new_contact.old_address = getattr(old, 'address', None)
        new_contact.contact_id = getattr(old, 'id', None)
        new_contact.automatic = new_contact.contact_id is None
        if not new_contact.old_address:
            new_contact.new_address = new.address
            new_contact.action = 'added'
            return new_contact
        if (getattr(old, 'id', None) is None and not new_contact.automatic
                and not getattr(new, 'address', None)):
            new_contact.end_date = coog_date.add_day(self.effective_date, -1)
            new_contact.action = 'ended'
            return new_contact
        if new.address and new.address != old.address:
            new_contact.new_address = new.address
            new_contact.action = 'new_address'
            new_contact.end_date = coog_date.add_day(self.effective_date, -1)
            return new_contact
        new_contact.action = 'nothing'
        return new_contact


class ContactDisplayer(model.CoogView):
    'Contact Displayer'

    __name__ = 'endorsement.manage_contacts.contact'

    action = fields.Selection([('nothing', ''), ('ended', 'Ended'),
        ('added', 'Added'), ('new_address', 'New Address')], 'Action',
        domain=[If(In(Eval('action', ''), ['ended', 'new_address']),
                ('action', 'in', ('ended', 'new_address', 'nothing')),
                If(Eval('action') == 'added',
                    ('action', 'in', ('added', 'removed')),
                    If(~Eval('contact_id', False),
                        ('action', 'in', ('new_address', 'nothing')),
                        If(~Eval('party', False),
                            ('action', '=', 'added'),
                            ('action', 'in',
                                ('ended', 'new_address', 'nothing'))))
                    ))],
        depends=['action', 'contact_id', 'party'])
    contract = fields.Many2One('endorsement.contract', 'Contract',
        readonly=True)
    contract_rec_name = fields.Char('Contract', readonly=True)
    party = fields.Many2One('party.party', 'Party', states={
            'readonly': Eval('action', '') != 'added'})
    kind = fields.Many2One('contract.contact.type', 'Kind', states={
            'readonly': Eval('action', '') != 'added'})
    old_address = fields.Many2One('party.address', 'Old Address',
        readonly=True)
    new_address = fields.Many2One('party.address', 'New Address',
        domain=[('party', '=', Eval('party')),
            ['OR', ('end_date', '=', None), ('end_date', '>=',
                    Eval('effective_date'))],
            ['OR', ('start_date', '=', None), ('start_date', '<=',
                    Eval('effective_date'))],
            If(~Eval('old_address', False), [],
                ['OR', ('id', '=', None), ('id', '!=', Eval('old_address'))]),
            ],
        states={'readonly': Eval('action', '') == 'ended',
            'required': In(Eval('action', ''), ['added', 'new_address'])},
        depends=['action', 'effective_date', 'old_address', 'party'])
    contact_id = fields.Integer('Contact Id', readonly=True)
    end_date = fields.Date('End Date', readonly=True)
    automatic = fields.Boolean('Calculated Automatically', readonly=True)
    effective_date = fields.Date('Effective Date', readonly=True)

    @fields.depends('action', 'contact_id', 'effective_date', 'end_date',
        'new_address')
    def on_change_action(self):
        if self.action == 'nothing':
            self.new_address = None
            if self.contact_id:
                self.end_date = Pool().get('contract.contact')(
                    self.contact_id).end_date
            else:
                self.end_date = None
        elif self.action == 'ended' and self.contact_id:
            self.end_date = coog_date.add_day(self.effective_date, -1)
            self.new_address = None
        elif self.action == 'added':
            self.end_date = None
        elif self.action == 'new_address':
            self.end_date = coog_date.add_day(self.effective_date, -1)

    @fields.depends('action', 'contact_id', 'effective_date', 'new_address',
        'old_address')
    def on_change_new_address(self):
        if (self.old_address and self.new_address and
                self.old_address == self.new_address):
            self.action = 'nothing'
        elif self.action == 'nothing':
            self.action = 'new_address'
        self.on_change_action()

    def to_contact(self):
        return Pool().get('contract.contact')(
            type=self.kind, party=self.party, date=self.effective_date,
            address=self.new_address, end_date=None)


class SelectEndorsement(model.CoogView):
    'Select Endorsement'

    __name__ = 'endorsement.start.select_endorsement'

    applicant = fields.Many2One('party.party', 'Applicant')
    contract = fields.Many2One('contract', 'Contract')
    effective_date = fields.Date('Effective Date', states={
            'invisible': ~Bool(Eval('endorsement_definition', False))})
    endorsement = fields.Many2One('endorsement', 'Endorsement',
        states={'invisible': True})
    endorsement_definition = fields.Many2One('endorsement.definition',
        'Endorsement', domain=[
            [('id', 'in', Eval('endorsement_definition_candidates', []))],
            [('is_technical', '=', False)],
            ['OR', [
                    If(Bool(Eval('product', False)),
                        [('products', '=', Eval('product'))],
                        [])],
                [('products', '=', None)]]],
        depends=['product', 'endorsement_definition_candidates'])
    endorsement_summary = fields.Text('Endorsement Summary')
    product = fields.Many2One('offered.product', 'Product', readonly=True,
        states={'invisible': True})
    has_preview = fields.Boolean('Has Preview', readonly=True,
        states={'invisible': True})
    contract_in_process = fields.Boolean('Contract in Progress',
        states={'invisible': True})
    contract_has_future_endorsement = fields.Boolean(
        'Contract has future endorsement', states={'invisible': True})
    effective_date_before_today = fields.Boolean('Effective date is in past',
        states={'invisible': True})
    endorsement_definition_candidates = fields.Many2Many(
        'endorsement.definition', None, None, 'Endorsement Definition')

    @classmethod
    def view_attributes(cls):
        return super(SelectEndorsement, cls).view_attributes() + [(
                '/form/group[@id="warnings"]/group[@id="contract_in_process"]',
                'states',
                {'invisible': Not(Eval('contract_in_process', False))}),
            (
                '/form/group[@id="warnings"]/group[@id="date_before_today"]',
                'states',
                {'invisible': Not(Eval('effective_date_before_today',
                            False))}),
            (
                '/form/group[@id="warnings"]/'
                'group[@id="contract_has_future_endorsement"]',
                'states',
                {'invisible': Not(Eval('contract_has_future_endorsement',
                            False))}
                )]

    @fields.depends('contract', 'contract_has_future_endorsement',
        'contract_in_process', 'effective_date')
    def on_change_contract(self):
        if self.contract:
            self.product = self.contract.product
            self.contract_in_process = bool(self.contract.current_state)
            self.contract_has_future_endorsement = len(
                Pool().get('endorsement.contract').search([
                        ('endorsement.effective_date', '>', self.effective_date
                            or utils.today()),
                        ('endorsement.state', '=', 'applied'),
                        ('contract', '=', self.contract.id)])) > 0
        else:
            self.product = None
            self.contract_in_process = None
            self.contract_has_future_endorsement = False

    @fields.depends('contract', 'contract_has_future_endorsement',
        'contract_in_process', 'effective_date', 'effective_date_before_today')
    def on_change_effective_date(self):
        if not self.effective_date:
            return
        self.effective_date_before_today = self.effective_date < utils.today()
        self.on_change_contract()

    def init_dict(self, data_dict):
        # Use rule engine API for future improved implementation
        data_dict.update({
                'contract': getattr(self, 'contract', None),
                'applicant': getattr(self, 'applicant', None),
                'date': self.effective_date,
                'endorsement_date': self.effective_date,
                'endorsement_definition': self.endorsement_definition,
                })

    def init_new_endorsement(self):
        endorsement = self._get_new_endorsement()
        endorsement.save()
        self.endorsement = endorsement.id

    def _get_new_endorsement(self):
        endorsement = Pool().get('endorsement')()
        endorsement.definition = self.endorsement_definition
        for fname in self._fields_to_copy():
            setattr(endorsement, fname, getattr(self, fname, None))
        if getattr(self, 'contract', None):
            endorsement.contract_endorsements = [{
                    'contract': self.contract.id,
                    'values': {},
                    }]
        return endorsement

    @staticmethod
    def default_endorsement_definition_candidates():
        pool = Pool()
        user = pool.get('res.user')(Transaction().user)
        candidates = pool.get('endorsement.definition').search([
                'OR', ('groups', '=', None),
                ('groups', 'in', [x.id for x in user.groups])])
        return [x.id for x in candidates]

    def _fields_to_copy(self):
        return ['applicant', 'effective_date']


class BasicPreview(EndorsementWizardPreviewMixin, model.CoogView):
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
    open_endorsement = StateAction('endorsement.act_generated_endorsement')
    summary_previous = StateTransition()
    preview_changes = StateTransition()
    dummy_step = StateView('endorsement.start.dummy_step', '', [])
    basic_preview = StateView('endorsement.start.preview_changes',
        'endorsement.preview_changes_view_form', [
            Button('Summary', 'summary', 'tryton-go-previous'),
            Button('Cancel', 'cancel', 'tryton-cancel'),
            Button('Apply', 'apply_endorsement', 'tryton-go-next',
                default=True),
            ])
    change_start_date = StateView('endorsement.contract.change_start_date',
        'endorsement.endorsement_change_contract_start_date_view_form', [
            Button('Previous', 'change_start_date_previous',
                'tryton-go-previous'),
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Suspend', 'change_start_date_suspend', 'tryton-save'),
            Button('Next', 'change_start_date_next', 'tryton-go-next',
                default=True)])
    change_start_date_previous = StateTransition()
    change_start_date_next = StateTransition()
    change_start_date_suspend = StateTransition()

    @classmethod
    def __setup__(cls):
        super(StartEndorsement, cls).__setup__()
        cls._error_messages.update({
                'cannot_resume_applied': 'It is not possible to resume an '
                'already applied endorsement',
                'erase_endorsement': 'Going on will erase all data on the '
                'endorsement.',
                'no_preview_defined': 'No preview state is defined on the '
                'endorsement definition',
                })

    @property
    def definition(self):
        if not self.select_endorsement:
            return None
        return self.select_endorsement.endorsement_definition

    @property
    def endorsement(self):
        if not self.select_endorsement:
            return None
        return getattr(self.select_endorsement, 'endorsement', None)

    def transition_start(self):
        if Transaction().context.get('active_model') != 'endorsement':
            return 'select_endorsement'
        endorsement = Pool().get('endorsement')(
            Transaction().context.get('active_id'))
        if endorsement.state == 'applied':
            self.raise_user_error('cannot_resume_applied')
        self.select_endorsement.endorsement = endorsement
        self.select_endorsement.applicant = endorsement.applicant
        if endorsement.contracts:
            self.select_endorsement.contract = endorsement.contracts[0].id
            self.select_endorsement.product = \
                endorsement.contracts[0].product.id
        self.select_endorsement.effective_date = endorsement.effective_date
        self.select_endorsement.endorsement_definition = \
            endorsement.definition.id
        return 'start_endorsement'

    def default_select_endorsement(self, name):
        if self.endorsement:
            self.raise_user_warning(str(self.endorsement.id),
                'erase_endorsement')
            self.endorsement.delete([self.endorsement])
            self.select_endorsement.endorsement = None
        if self.select_endorsement._default_values:
            return self.select_endorsement._default_values
        pool = Pool()
        Date = pool.get('ir.date')
        EndorsementContract = pool.get('endorsement.contract')
        if Transaction().context.get('active_model') == 'contract':
            contract = pool.get('contract')(
                Transaction().context.get('active_id'))
            EndorsementContract.check_contracts_status([contract, ])
            return {
                'effective_date': max(contract.start_date
                    or contract.initial_start_date, Date.today()),
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
        with model.error_manager():
            self.check_before_start()
        if not self.endorsement:
            self.select_endorsement.init_new_endorsement()
        return self.definition.endorsement_parts[0].view

    def check_before_start(self):
        definition = self.select_endorsement.endorsement_definition
        for part in definition.endorsement_parts:
            view = getattr(self, part.view)
            data_dict = {}
            self.select_endorsement.init_dict(data_dict)
            if view.must_skip_step(data_dict):
                if len(definition.endorsement_parts) > 1:
                    # Check errors only if this is the only state, to display
                    # something to the user
                    continue
            view.check_before_start(self.select_endorsement)

    def default_summary(self, name):
        result = self.select_endorsement._default_values
        result['endorsement_summary'] = \
            self.endorsement.endorsement_summary
        result['has_preview'] = bool(self.endorsement.definition.preview_state)
        return result

    def transition_summary_previous(self):
        return self.get_state_before('')

    def transition_preview_changes(self):
        if not self.endorsement.definition.preview_state:
            self.raise_user_error('no_preview_defined')
        return self.endorsement.definition.preview_state

    def default_basic_preview(self, name):
        BasicPreview = Pool().get('endorsement.start.preview_changes')
        preview_values = self.endorsement.extract_preview_values(
            BasicPreview.extract_endorsement_preview)
        return BasicPreview.init_from_preview_values(preview_values)

    def transition_apply_endorsement(self):
        Endorsement = Pool().get('endorsement')
        with Transaction().set_context(_check_access=True):
            Endorsement.apply([self.endorsement])
        # Look for possibly created endorsements
        next_endorsements = Endorsement.search([
                ('generated_by', '=', self.endorsement)])
        if not next_endorsements:
            return 'end'
        return 'open_endorsement'

    def do_open_endorsement(self, action):
        Endorsement = Pool().get('endorsement')
        # Look for possibly created endorsements
        next_endorsements = [x.id
            for x in Endorsement.search([
                    ('generated_by', '=', self.endorsement)])]
        action['domains'] = []
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('id', 'in', next_endorsements)])
        return action, {'res_id': next_endorsements}

    def transition_change_start_date_previous(self):
        self.end_current_part('change_start_date')
        return self.get_state_before('change_start_date')

    def transition_change_start_date_suspend(self):
        self.end_current_part('change_start_date')
        return 'end'

    def default_change_start_date(self, name):
        State = Pool().get('endorsement.contract.change_start_date')
        contract = self.select_endorsement.contract
        endorsement_part = self.get_endorsement_part_for_state(
            'change_start_date')
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

    def transition_change_start_date_next(self):
        self.end_current_part('change_start_date')
        return self.get_next_state('change_start_date')

    def get_state_before(self, state_name):
        pool = Pool()
        all_states = self.get_endorsement_states()
        data_dict = {}
        self.select_endorsement.init_dict(data_dict)
        for part in reversed(self.definition.endorsement_parts):
            if not state_name:
                if pool.get(all_states[part.view]).must_skip_step(data_dict):
                    continue
                return part.view
            if part.view == state_name:
                state_name = ''
        return 'start'

    def get_next_state(self, current_state):
        pool = Pool()
        all_states = self.get_endorsement_states()
        data_dict = {}
        self.select_endorsement.init_dict(data_dict)
        found = False
        for part in self.definition.endorsement_parts:
            if part.view == current_state:
                found = True
            elif found:
                if pool.get(all_states[part.view]).must_skip_step(data_dict):
                    continue
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
            # Do NOT enable this unless you launch all endorsement modules
            # tests (including scenarios) and they PASS !
            # result[state_name] = coog_string.translate_model_name(
            #     pool.get(state.model_name))
            result[state_name] = state.model_name
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

    def get_endorsed_object(self, endorsement_part):
        # TODO : Update once multiple objects may be changed
        return self.select_endorsement.contract

    @classmethod
    def get_fields_to_get(cls, model, view_id):
        fields_def = Pool().get(model).fields_view_get(view_id)
        return fields_def['fields'].keys()

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


add_endorsement_step(StartEndorsement, RecalculateContract,
    'recalculate_contract')

add_endorsement_step(StartEndorsement, ReactivateContract,
    'reactivate_contract')

add_endorsement_step(StartEndorsement, ChangeContractExtraData,
    'change_contract_extra_data')

add_endorsement_step(StartEndorsement, TerminateContract, 'terminate_contract')

add_endorsement_step(StartEndorsement, VoidContract, 'void_contract')

add_endorsement_step(StartEndorsement, ManageOptions, 'manage_options')

add_endorsement_step(StartEndorsement, ChangeContractSubscriber,
    'change_contract_subscriber')

add_endorsement_step(StartEndorsement, ManageContacts, 'manage_contacts')


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
                '_datetime': endorsement.rollback_date,
                '_datetime_exclude': True,
                })
        return action, {}


class EndorsementSelectDeclineReason(model.CoogView):
    'Reason selector to decline endorsement'

    __name__ = 'endorsement.decline.select_reason'

    endorsements = fields.One2Many('endorsement', None, 'Endorsements',
        readonly=True)
    reason = fields.Many2One('endorsement.sub_state', 'Reason', required=True,
        domain=[('state', '=', 'declined')])


class EndorsementDecline(model.CoogWizard):
    'Decline Endorsement Wizard'

    __name__ = 'endorsement.decline'
    start_state = 'select_reason'
    select_reason = StateView(
        'endorsement.decline.select_reason',
        'endorsement.select_endorsement_decline_reason_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Decline', 'decline', 'tryton-go-next', default=True),
            ])
    decline = StateTransition()

    def default_select_reason(self, name):
        assert Transaction().context.get('active_model') == 'endorsement'
        active_ids = Transaction().context.get('active_ids')
        return {
            'endorsements': active_ids,
            }

    def transition_decline(self):
        pool = Pool()
        Endorsement = pool.get('endorsement')
        reason = self.select_reason.reason
        active_ids = Transaction().context.get('active_ids')
        selected_endorsements = Endorsement.search([('id', 'in', active_ids)])
        Endorsement.decline(selected_endorsements, reason=reason)
        return 'end'
