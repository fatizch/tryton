import copy
import functools

# Needed for displaying objects
from trytond.model import fields

from trytond.modules.coop_utils import utils, CoopView, CoopSQL
from trytond.modules.coop_utils import WithAbstract

# Needed for proper encoding / decoding of objects as strings
from trytond.protocols.jsonrpc import object_hook

# Needed for Wizardry
from trytond.wizard import Wizard, Button, StateView, StateTransition
from trytond.wizard import StateAction

# Needed for getting models
from trytond.pool import Pool

# Needed for resuming processes
from trytond.transaction import Transaction

from trytond.pyson import Eval

# Needed for serializing data
try:
    import simplejson as json
except ImportError:
    import json


__all__ = ['WithAbstract', 'ProcessState', 'CoopProcess', 'CoopStateView',
           'CoopStep', 'CoopStepView', 'DependantState', 'SuspendedProcess',
           'ResumeWizard']


ACTIONS = ('go_previous', 'go_next', 'cancel', 'complete', 'check', 'suspend')


class ProcessState(CoopView):
    '''
        This class is a fake step. Its only purpose is to provide us with a
        place to store all process-related persistent data.

        As we want something more dynamic than the default tryton wizards, we
        typically need to know where we are in the process and what we are
        doing. That's what this step is for.
    '''
    __name__ = 'ins_process.process_state'

    # This is what we currently are trying to do. This field is set in the
    # transition steps associated to the buttons, before calling the master
    # transition.
    cur_action = fields.Selection(
                    [(action, action) for action in list(ACTIONS)],
                    'Current Action')

    # This is a link to the process descriptor, which is a kind of client
    # business rule.
    # It is the object that knows the step order, and a few other things.
    process_desc = fields.Many2One('ins_process.process_desc',
                                   'Process Description')

    # This is the name of the current step as in the standard tryton wizard.
    # That is, it is the name of the field representing the current step.
    cur_step = fields.Char('Current step')

    # And this it the link to its process descriptor. Both those references are
    # updated in the calculate_next_step method
    cur_step_desc = fields.Many2One('ins_process.step_desc',
                                    'Step Descriptor')

    # This field will be used to store the suspended process which started the
    # current process (if it exists) so that we can write over it in case of
    # suspension, delete in case of completion/cancellation.
    from_susp_process = fields.Integer('From Process')

    # Stores the list of errors for displaying
    errors = fields.Text('Errors')

    # Stores the product for product-based state definition :
    on_product = fields.Many2One('ins_product.product',
                                  'On Product Process')

    @classmethod
    def __setup__(cls):
        if '__abstracts__' in dir(cls):
            for (field_name, field_model) in getattr(cls, '__abstracts__'):
                setattr(
                    cls,
                    field_name + '_db',
                    fields.Many2One(field_model, field_name))
                setattr(
                    cls,
                    field_name + '_str',
                    fields.Text('Json' + field_name))
        return super(ProcessState, cls).__setup__()


class CoopProcess(Wizard):
    '''
        This class will serve as a master for all process classes.

        It is designed to look for defining rules in the database, which will
        define how the process is supposed to flow.

        There will be only one virtual step, which will use the rules to
        calculate its behaviour. It includes validation rules, applicability
        rules (should we go through the process or step over), and
        next/previous step calculation.

        There will be a library of steps in which the rules will look for.
    '''
    __name__ = 'ins_process.coop_process'

    config_data = {
        'process_state_model': 'ins_process.process_state'
        }

    # Starting step, will be the same for all processes
    start_state = 'steps_start'

    # steps_start is a virtual step. So we just define it as a transition state
    # so that the transition_steps_start can be overriden in child classes.
    steps_start = StateTransition()

    # This step is the most important of all. It is the one that will manage
    # the execution flow through the use of session.process_data[cur_step] to
    # get the current step, and calls to CoopStep submethods.
    master_step = StateTransition()

    # Those steps are all virtual steps, whose transition method will be called
    # every time that someone clicks on a button.
    # A few actions (typically, setting session.process_state.cur_action) will
    # be performed before calling master_step
    steps_next = StateTransition()
    steps_previous = StateTransition()
    steps_cancel = StateTransition()
    steps_complete = StateTransition()
    steps_suspend = StateTransition()
    steps_check = StateTransition()
    steps_terminate = StateTransition()

    @classmethod
    def __setup__(cls):
        def get_config(name, config_dict={}):
            if name in config_dict:
                return config_dict[name]
            else:
                return None

        # This is not a real state, it will only be used as a storage step for
        # the process' data

        setattr(cls, 'get_config',
            functools.partial(get_config, config_dict=cls.config_data))

        cls.process_state = StateView(
            cls.get_config('process_state_model'),
            '',
            [])

        super(CoopProcess, cls).__setup__()

    def init_session(self):
        # Abstract objects must be initialized. This must be done for each one
        # of those defined in the process_state.
        self.process_state.errors = ''
        for elem in set([elem for elem in dir(self.process_state)
                     if (elem[-3:] == '_db' or elem[-4:] == '_str')]):
            # Every field matching the '_db' or the '_str' pattern will be
            # considered as an abstract field, and initialized.
            if not hasattr(self.process_state, elem):
                setattr(self.process_state, elem, 0)
            if not hasattr(self.process_state, elem):
                setattr(self.process_state, elem, '')
        self.process_state.on_product = 0
        for elem in dir(self.process_state):
            if elem[:-4] == '_str':

                setattr(self.process_state, elem, '')

    def add_error(self, error):
        # We needed a common entry-point for all error creation.
        # Errors are stored in the process_state.errors field, which will be
        # used when the errors are displayed.
        errors = utils.to_list(error)
        self.process_state.errors += '\n'.join(errors)

    def resume_suspended(self):
        # Here we want to resume a previously suspended process.
        SuspendedProcess = Pool().get('ins_process.suspended_process')
        try:
            susp_process = SuspendedProcess(
                Transaction().context.get('active_id'))
        except KeyError:
            susp_process = None

        # If a suspended process is found in the current context, resume it
        if susp_process:
            # We get a dictionnary with the data from the stored session
            susp_data = json.loads(susp_process.session_data.encode('utf-8'),
                                   object_hook=object_hook)
            # Then update everything.
            # This code comes from the execute method of wizard.py
            for state_name, state in self.states.iteritems():
                if isinstance(state, StateView):
                    Target = Pool().get(state.model_name)
                    susp_data.setdefault(state_name, {})
                    setattr(self, state_name, Target(**susp_data[state_name]))

            # We store the fact that the process comes from a previously
            # suspended process in order to write rather than create, and to
            # be able to delete the suspended process from the db when
            # completing the process (going through the 'terminate' state)
            self.process_state.from_susp_process = susp_process.id
            self.dirty = True
        else:
            # Of course, Trying to resume an inexisting process raises an
            # error.
            self.raise_user_error('Could not find process to init from')

    # We use the fact that we know the start step to set up a few things
    def transition_steps_start(self):
        # We check if we are currently trying to resume a suspended process
        if (Transaction().context.get('active_model')
                            == 'ins_process.suspended_process'):
            self.resume_suspended()
            return self.process_state.cur_step

        # If not, we go on and start a new process
        # First of all, we get and set the process descriptor.
        ProcessDesc = Pool().get('ins_process.process_desc')
        try:
            res, = ProcessDesc.search([
                    ('process_model', '=', self.__name__)],
                limit=1)
        except Exception:
            # If no process desc is found, we raise an error and exit the
            # process.
            res = None
        if not res:
            self.raise_user_error('Could not find a process descriptor for %s,\
                                    \nplease contact software admin.'
                                    % self.__class__.coop_process_name())
            return 'end'

        self.process_state.process_desc = res

        self.init_session()

        # We then asks the process desc which one is the first step
        (step_obj, step_name) = \
            self.process_state.process_desc.get_first_step_desc()

        # We use the answer to look for the associated state name (step_desc
        # associations are based on coop_step_name() calls)
        _, first_step_name = self.get_state_from_model(step_name)

        # We use the process_state's fields to store those persistent data :
        self.process_state.cur_step = first_step_name
        self.process_state.cur_step_desc = step_obj.id

        # Now the work begins : we get the current state
        state = getattr(self, first_step_name)

        # And initialize the steps (exiting in case of errors)
        (res, errors) = state.do_before(self, step_obj)
        if not res:
            self.raise_user_error('Could not initialize process, exiting\n'
                                  + '\n'.join(errors))
            return 'end'

        # Time to display
        return first_step_name

    @staticmethod
    def coop_process_name():
        '''
            This method is used as a label for the wizard, it is
            supposed to be unique, so that it can be used as a key when
            creating the process descs.

            All 'real' process classes will inherit from this one, so we must
            not return a result, as it should never be instanciated.
        '''
        return ''

    def get_state_from_model(self, step_model):
        # Here we go through the states defined on the current process, in
        # order to find which one corresponds to the model provided by the
        # process desc
        for state in self.states:
            # No need to go through those which are not StateViews
            if (isinstance(self.states[state], StateView)
                and self.states[state].model_name == step_model):
                # We returned both the state object and its name.
                return (self.states[state], state)

    def transition_master_step(self):
        '''
            This method will be called every time a flow button is clicked.
            The transition_steps_* will set a few things in
            session.process_state (typically cur_action) so that we are
            able to know where we are in the process flow.
        '''
        # Being cautious, we store the current step name, as it will be
        # modified during calculation.
        from_step = self.process_state.cur_step

        # Now we call calculate_next_step, which will use the data
        # available in the session object to compute where we should go,
        # depending on where we currently are and the cur_action.
        res = self.calculate_next_step()

        # Just to be sure...
        if res == '':
            self.add_error('Could not calculate next step')
            res = from_step

        # We store the new state name (even though it should already be
        # done.
        self.process_state.cur_step = res

        # We get the errors
        errors = self.process_state.errors
        if len(errors) > 0:
            # If there are some, we clear them.
            self.process_state.errors = ''

            # We need to save again, as raise_user_errors drops the session
            self._save()

            # And we finally display them
            self.raise_user_error(errors)

        # and we save the session
        self._save()
        return res

    # Transition method, we just set cur_action for now, and call master_step
    def transition_steps_next(self):
        self.process_state.cur_action = 'go_next'
        return 'master_step'

    # Transition method, we just set cur_action for now, and call master_step
    def transition_steps_previous(self):
        self.process_state.cur_action = 'go_previous'
        return 'master_step'

    # Transition method, we just set cur_action for now, and call master_step
    def transition_steps_cancel(self):
        self.process_state.cur_action = 'cancel'
        return 'master_step'

    # Transition method, we just set cur_action for now, and call master_step
    def transition_steps_complete(self):
        self.process_state.cur_action = 'complete'
        return 'master_step'

    # Transition method, we just set cur_action for now, and call master_step
    def transition_steps_check(self):
        self.process_state.cur_action = 'check'
        return 'master_step'

    # Transition method, we just set cur_action for now, and call master_step
    def transition_steps_suspend(self):
        self.process_state.cur_action = 'suspend'
        return 'master_step'

    # This step will be called in case of soft termination (cancel or complete)
    # We need to delete the suspended_process object if it exists
    def transition_steps_terminate(self):
        if hasattr(self.process_state, 'from_process'):
            from_process = self.process_state.from_susp_process
            SuspendedProcess = Pool().get('ins_process.suspended_process')
            SuspendedProcess.delete([from_process])
        return 'end'

    # This method will be called when clicking on the 'complete' button
    def do_complete(self):
        return (True, [])

    def calculate_next_step(self):
        '''
            This method is used to calculate the name of the next step to
            execute. It can call itself if needed.
        '''
        Date = Pool().get('ir.date')
        # We just need to get a few things at start:
        #    Current state model ('ins_process.process_name.step_name')
        cur_state = getattr(self, self.process_state.cur_step)
        #    Current action : what do we want to do ?
        cur_action = self.process_state.cur_action
        #    Current step descriptor : a 'ins_process.step_desc' object
        #    whose step_model field would be cur_state_model
        cur_step = self.process_state.cur_step_desc
        #    Current process descriptor : this one is already stored
        #    in session.process_state
        cur_process = self.process_state.process_desc

        # Here we go : we switch case based on cur_action :
        if cur_action == 'check':
            # CHECK :
            # Well, just call check_step
            (res, errors) = cur_state.check_step(self, cur_step)
            # and save the result
            if not res:
                self.add_error(errors)
            else:
                self.add_error('Everything is OK')
            return self.process_state.cur_step
        elif cur_action == 'cancel':
            # CANCEL :
            # End of the process
            return 'steps_terminate'
        elif cur_action == 'complete':
            # COMPLETE :
            # First we try to complete the current step :
            (res, errors) = cur_state.do_after(self, cur_step)
            # If we cannot, we stay where we are
            if not res:
                self.add_error(errors)
                return self.process_state.cur_step

            # If we can, we call the do_complete method on the process
            (res, errors) = self.do_complete()
            # If it works, end of the process
            if res:
                return 'steps_terminate'
            # else, back to current step...
            self.add_error(errors)
            return self.process_state.cur_step
        elif cur_action == 'go_previous':
            # PREVIOUS :
            # We need to get the previous step from the process desc
            next_step = cur_process.get_prev_step(cur_step)
            # We go back until we got a non virtual step.
            while next_step.virtual_step == True:
                next_step = cur_process.get_prev_step(next_step)
            # If it does not exist, no need to go further
            if next_step == cur_step:
                return self.process_state.cur_step
            # Now, we get our tools : step name, model, view
            (_, next_state_name) = self.get_state_from_model(
                next_step.get_step_model(self.process_state.on_product))
            if next_state_name == '':
                self.add_error('Could not find step model')
                return ''

            next_state = getattr(self, next_state_name)
            # Should we display this step ?
            (res, errors) = next_state.must_step_over(self, next_step)

            if not res:
                # Yes => here we go (no need to call the before method, we do
                # not want to reset the step)
                self.process_state.cur_step = next_state_name
                self.process_state.cur_step_desc = next_step.id
                return self.process_state.cur_step
            else:
                # No => ok, we just set this step as the current step, and
                # we go on.
                self.process_state.cur_step = next_state_name
                self.process_state.cur_step_desc = next_step.id
                # (Here we suppose that the first step will never be stepped
                # over, we might have to change a few things if it happens to
                # be possible)
                return self.calculate_next_step()
        elif cur_action == 'go_next':
            # NEXT :
            # As for previous, we get the next step from the process desc
            next_step = cur_process.get_next_step(cur_step)
            # and we exit now if it does no exist
            if next_step == cur_step:
                return self.process_state.cur_step
            # First of all we go on until we find a non-virtual step
            while next_step.virtual_step == True:
                result = False
                errors = []
                # We call the step_over methods
                for res, errs in CoopStepMethods.call_client_rules(
                                            self,
                                            '0_step_over',
                                            next_step):
                    if res != False:
                        result = res
                        errors += errs
                # In case of error, we stop here then go back to the step
                if errors != []:
                    self.add_error(errors)
                    # A '' return value will make it so we stay on the
                    # current step
                    return ''
                if result == False:
                    # We must call the check methods :
                    result = True
                    errors = []
                    # We call the step_over methods
                    for res, errs in CoopStepMethods.call_client_rules(
                                            self,
                                            '2_check_step',
                                            next_step):
                        if res != True:
                            result = res
                            errors += errs
                    if result == False:
                        self.add_error(errors)
                        return ''
                next_step = cur_process.get_next_step(next_step)
            # If it does not exist, no need to go further
            if next_step == cur_step:
                return self.process_state.cur_step
            # Now, we get our tools : step name, model, view
            (_, next_state_name) = self.get_state_from_model(
                next_step.get_step_model(self.process_state.on_product))
            next_state = getattr(self, next_state_name)
            # And we try to finish the current step
            (res, errors) = cur_state.do_after(self, cur_step)
            if not res:
                # If it does not work, we stop here
                self.add_error(errors)
                return self.process_state.cur_step
            else:
                # If it works, we call the before of the next method
                (res, errors) = next_state.do_before(self, next_step)
                if not res:
                    # Again, it it does not work, we stop right here
                    self.add_error(errors)
                    return self.process_state.cur_step
                # Now we must check that the step should be displayed
                (res, errors) = next_state.must_step_over(self, next_step)
                # We set the step as the current step anyway
                self.process_state.cur_step = next_state_name
                self.process_state.cur_step_desc = next_step.id
                if not res:
                    # We must not step over, it ends here
                    return self.process_state.cur_step
                else:
                    # We must step over, so we just calculate_next_step
                    # again. Note that it supposed that the last step will
                    # not be stepped over !
                    return self.calculate_next_step()
        elif cur_action == 'suspend':
            # SUSPEND :
            # We create or find a suspended process, then store the current
            # process session data in it.
            SuspendedProcess = Pool().get('ins_process.suspended_process')
            SessionObj = Pool().get('ir.session.wizard')
            the_session = SessionObj(self._session_id)
            data_dict = {
                'suspension_date': Date.system_today(),
                'for_user': the_session._user,
                'desc': '%s, step %s' % (
                    self.coop_process_name(),
                    cur_state.coop_step_name()),
                'process_model_name': self.__name__,
                # We need the session_data to be persistent in order
                # to be able to resume the process in the same state
                # as it was before, so we encode it in a json string.
                'session_data': the_session.data
                }
            if (hasattr(self.process_state, 'from_susp_process') and
                                self.process_state.from_susp_process > 0):
                # Already exist, we just need an update
                SuspendedProcess.write([self.process_state.from_susp_process],
                                       data_dict)
            else:
                # Does not exist, create it !
                process = SuspendedProcess.create(data_dict)
                if not process:
                    self.raise_user_error('Could not store process !')
            return 'end'
        # Just in case...
        return self.process_state.cur_step


class CoopState(object):
    '''
        This class is going to be used as a parent for all step classes.

        It defines :
            - a step_over method, which will be called to decide if the step
            should be displayed or stepped over
            - a before_step method, which is the code that must be executed
            before displaying the step
            - a check_step method, which will be called in order to check
            data consistency
            - a post_step method, which will be called if the user clicks on
            the next button, and if the check_step method returns 'True'

        Ultimately, we will need a way to calculate whether or not a given
        button must be displayed or not.
    '''

    @staticmethod
    def button_next():
        return Button('Next',
                      'steps_next',
                      'tryton-go-next')

    @staticmethod
    def button_previous():
        return Button('Previous',
                      'steps_previous',
                      'tryton-go-previous')

    @staticmethod
    def button_cancel():
        return Button('Cancel',
                      'steps_cancel',
                      'tryton-cancel')

    @staticmethod
    def button_complete():
        return Button('Complete',
                      'steps_complete',
                      'tryton-ok')

    @staticmethod
    def button_check():
        return Button('Check',
                      'steps_check',
                      'tryton-help')

    @staticmethod
    def button_suspend():
        return Button('Suspend',
                      'steps_suspend',
                      'tryton-go-jump')

    # For convenience, a list of all buttons...
    @staticmethod
    def all_buttons():
        return [CoopState.button_previous(),
                CoopState.button_check(),
                CoopState.button_next(),
                CoopState.button_complete(),
                CoopState.button_suspend(),
                CoopState.button_cancel()]


class CoopStateView(StateView, CoopState):
    '''
        This class is an extension of CoopState which will allow us to easily
        create step classes.

        To use, just create an instance with the name of the model and view,
        buttons will be calculated automatically.
    '''

    # Right now, we can only use the all_buttons method to automatically add
    # all the buttons for each View
    def __init__(self, name, view):
        super(CoopStateView, self).__init__(name,
                                            view,
                                            CoopState.all_buttons())

    # Here is a little dirty trick to avoid resetting of StateView values after
    # before methods.
    # All field initialization should be done through 'before' methods
    def get_defaults(self, wizard, state_name, fields):
        res = super(CoopStateView, self).get_defaults(wizard,
                                                      state_name,
                                                      fields)
        # First we get the existing data for our step in the current session
        default_data = getattr(wizard, state_name)
        if default_data:
            # If it exists, we go through each field and set a new entry in the
            # return dict
            for field in fields:
                if hasattr(default_data, field):
                    field_value = getattr(default_data, field)
                    # We need to make the field json-compatible, so we use the
                    # serialize_field function which does exactly that.
                    res[field] = WithAbstract.serialize_field(field_value)

        return res

    def get_buttons(self, wizard, state_name):
        # As a default behaviour, all CoopStateView declarations append all
        # available buttons to the state definition.
        #
        # That allows to fine-tune displayed buttons through the process_desc
        # records use. Here we use those records to filter which buttons will
        # be displayed on the state.

        # First of all, we got a list of all available buttons.
        buttons = super(CoopStateView, self).get_buttons(wizard,
                                                         state_name)

        # Then we get the current process_desc, so that we can iterate on its
        # steps.
        ProcessDesc = Pool().get('ins_process.process_desc')
        process_desc, = ProcessDesc.search([
                                    ('process_model', '=', wizard.__name__)],
                                           limit=1)
        res_buttons = []
        for step_desc in process_desc.steps:
            # We need to get the state_obj associated to the step.
            state_obj = Pool().get(self.model_name)
            # In the case of dependant step, it becomes trickier. We need to
            # find the step_desc which matches the state we currently are
            # working on.
            #
            # In any case, we loop on the step_descs until we find one that
            # matches the current state.
            if state_obj in DependantState.__subclasses__():
                if (not state_obj.depends_on_state() ==
                                                step_desc.product_step_name):
                    continue
            elif self.model_name != step_desc.step_model:
                continue

            # We get the default button name
            default_button = step_desc.button_default
            for button in buttons:
                # For each available button, if it is defined in the step_desc,
                # we append it to the result list.
                #
                # If we found one that matches the default_button, we set it.
                if getattr(step_desc, 'button' + button['state'][5:]):
                    if default_button[7:] == button['state'][6:]:
                        button['default'] = True
                    res_buttons.append(button)
            break
        return res_buttons


class CoopStepMethods(object):
    '''
        This is the step master class. It defines a step, allows to create a
        view for this step, and has all the methods needed for going through
        the process :
            step_over
            before
            check
            after
        Those methods will look for methods matching a certain pattern (prefix)
        and call them. It will then (if necessary) look for client defined
        rules, and call them as well.
    '''
    # cf coop_process_name, this method is used as a label for representing
    # the step class when creating step descs.
    # All child classes designed to be instanciated must override this method.
    @staticmethod
    def coop_step_name():
        return ''

    @classmethod
    def get_methods_starting_with(cls, prefix):
        # This method is used to get all methods of the class that start with
        # the provided prefix
        res = [getattr(cls, method)
                   for method in dir(cls)
                   if (callable(getattr(cls, method))
                       and method.startswith(prefix))]

        # Methods which will be defined can have a 'priority' assigned to them.
        # This can be done by using the @priority(value) decorator on them.
        #
        # Here we use this data to sort the methods that will be executed
        def comp_func(f1, f2):
            # No priority defined means 'do not care'.
            if hasattr(f1, 'priority'):
                if hasattr(f2, 'priority'):
                    # Equal priority returns 0. We might want to return an
                    # error instead, there should be no doubt on which method
                    # comes first.
                    if f1.priority == f2.priority:
                        return 0
                    # Lower number means higher priority.
                    if f1.priority < f2.priority:
                        return 1
                    return -1
                # If f1 has a priority defined and not f2, then f1 wins
                return 1
            # Idem, if f1 has no priority and f2 does, f2 wins
            if hasattr(f2, 'priority'):
                return -1
            return 0

        res.sort(cmp=comp_func)

        return res

    @staticmethod
    def fill_data_dict(wizard, data_pattern):
        '''
            This method is a core method.
            It takes a data pattern as an input, that is a structure asking for
            data.

            It uses this pattern to go through the session to get the required
            values and send them back, so that client side rules can use them.

            return value should look like :
                {'ins_process.contract': {
                                            'start_date': some_value,
                                            'contract_number': other_value
                                            },
                 'ins_process.extension': { ... }
                         etc...
                }
        '''
        return {}

    @staticmethod
    def call_client_rules(wizard, rulekind, step_desc):
        '''
            This method will look for and call the client defined ruler in the
            step_desc, which match the rulekind.
            It then asks the rule which data are needed for execution, fetchs
            the data and call the rule.

            It is intended to be use as an iterator which will yield the result
            of each call, which is a tuple containing the result and a list of
            errors.
        '''

        # We iterate through the list of existing methods on the step_desc
        # which match our rule_kind
        for rule in step_desc.get_appliable_rules(rulekind):
            # We get the needed data pattern for this method
            needed_data = rule.get_data_pattern()
            # Then we call the fill_data_dict, feed its result to the
            # method, and yield the result
            yield rule.calculate(rule,
                            CoopStepMethods.fill_data_dict(wizard,
                                                           needed_data))

    @classmethod
    def call_methods(cls, wizard, step_desc, prefix, default=True,
                        client_rules=''):
        '''
            This method will call all methods designed for the defined role.

            It will first iterate through the methods matching the prefix,
            then call and get the result.
            If the result value is not the default value, it return the result
            and the errors.
            If not, it calls the client side rules.
        '''
        # We get the list of methods
        methods = cls.get_methods_starting_with(prefix)
        (result, errors) = (default, [])
        # and execute each of them
        tmp_res = None
        for method in methods:
            #try:
            tmp_res = method.__call__(wizard)
            #except Exception, e:
            #    (res, error) = (not default, ['Internal Error in %s'
            #                                            % method.__name__])
            #    raise e

            if tmp_res:
                try:
                    (res, error) = tmp_res
                except TypeError:
                    (res, error) = (not default, ['Probably forgot to return a\
                                            value in %s' % method.__name__])
            if res != default:
                # We are only interested in the res != default case
                result = res
                errors += error
        if result == default:
            # Only if result is not default should we call client rules, that
            # should help in terms of performance
            if client_rules != '':
                # We get the result of each call and update the global result
                # accordingly
                for res, errs in cls.call_client_rules(
                        wizard,
                        client_rules,
                        step_desc):
                    if res != default:
                        result = res
                        errors += errs
        return (result, errors)

    def do_after(self, wizard, step_desc):
        '''
            This method executes what must be done after clicking on 'Next'
            on the step's view. It will first check for errors then, if
            everything is ok, will go through post_step methods.

            It is designed as to avoid to be instance dependant, that is it
            should be possible to call it through a batch to simulate for
            instance a manual subscription.
        '''
        # Check for errors in current view
        (res, check_errors) = self.check_step(wizard, step_desc)
        post_errors = []
        if res:
            # If there are errors, there is no need (and it would be dangerous)
            # to continue
            (res, post_errors) = self.post_step(wizard, step_desc)
        return (res, check_errors + post_errors)

    def do_before(self, wizard, step_desc):
        '''
            This method executes what must be done before displaying the step
            view. It might be initializing values, creating objects for
            displaying, etc... It should also check that everything which will
            be necessary for the step completion is available in the session.

            It is designed as to avoid to be instance dependant, that is it
            should be possible to call it through a batch to simulate for
            instance a manual subscription.
        '''
        (res, errors) = self.before_step(wizard, step_desc)
        return (res, errors)

    def must_step_over(self, wizard, step_desc):
        '''
            This method calculates whether it is necessary to display the
            current step view.

            It is designed as to avoid to be instance dependant, that is it
            should be possible to call it through a batch to simulate for
            instance a manual subscription.
        '''
        (res, errors) = self.step_over(wizard, step_desc)
        return (res, errors)

    def step_over(self, wizard, step_desc):
        # This is the actual call to the step_over_ methods and client rules
        return self.call_methods(wizard,
                                 step_desc,
                                 'step_over_',
                                 default=False,
                                 client_rules='0_step_over')

    def before_step(self, wizard, step_desc):
        # This is the actual call to the before_step_ methods
        return self.call_methods(wizard,
                                 step_desc,
                                 'before_step_')

    def check_step(self, wizard, step_desc):
        # This is the actual call to the check_step_ methods and client rules
        return self.call_methods(wizard,
                                 step_desc,
                                 'check_step_',
                                 client_rules='2_check_step')

    def post_step(self, wizard, step_desc):
        # This is the actual call to the post_step_ methods
        return self.call_methods(wizard,
                                 step_desc,
                                 'post_step_')


class NoSessionFoundException(Exception):
    '''
        Exception that will be raised in case of a One2Many target looking
        for a 'from_session' context that does not exist.
    '''
    pass


class CoopStepView(CoopView):
    '''
        This class will be used as a mother class for all non-state views
        for coop processes.
        For instance, if your current state needs a One2Many to represent
        data, you might need non-persistent class as a target.
        You will want to use this class as a model, as it proides some
        useful methods.
    '''

    @staticmethod
    def get_context():
        if ('from_session' in Transaction().context
                        and Transaction().context.get('from_session') > 0):
            Session = Pool().get('ir.session.wizard')
            session = Session(Transaction().context.get('from_session'))
            data = json.loads(session.data.encode('utf-8'))
            ProcessDesc = Pool().get('ins_process.process_desc')
            process_model = ProcessDesc(
                data['process_state']['process_desc']).process_model
            Wizard = Pool().get(process_model, type='wizard')
            the_wizard = Wizard(session.id)
            return the_wizard
        raise NoSessionFoundException


class CoopStep(CoopView, CoopStepMethods):
    '''
        This class aggregates the Methods of CoopStepMethods with the CoopView
        so that it can be use as steps for our processes.
    '''
    @classmethod
    def __setup__(cls):
        super(CoopStep, cls).__setup__()
        for field_name, field in ((field, getattr(cls, field))
                for field in dir(cls)):
            if hasattr(field, 'context') and isinstance(field,
                                                        fields.One2Many):
                cur_attr = getattr(cls, field_name)
                if cur_attr.context is None:
                    cur_attr.context = {}
                cur_attr.context['from_session'] = Eval('session_id')
                setattr(cls, field_name, copy.copy(cur_attr))

    # Warning : to work, this field must be added to the view that will be used
    # displaying the Step, even though it is invisible.
    session_id = fields.Integer('Session Id',
                                states={'invisible': True})


class DependantState(CoopStep):
    @classmethod
    def __setup__(cls):
        super(DependantState, cls).__setup__()

        @staticmethod
        def before_step_wizard_init(wizard):
            getattr(wizard,
                    cls.state_name()
                    ).session_id = wizard._session_id
            return (True, [])
        setattr(cls, 'before_step_wizard_init', before_step_wizard_init)

    @staticmethod
    def depends_on_state():
        pass

    @staticmethod
    def state_name():
        pass


class SuspendedProcess(CoopSQL, CoopView):
    '''
        This class represents a suspended process, which can be resumed later.
    '''
    __name__ = 'ins_process.suspended_process'

    # Just so we know since when the process has been suspended. In the
    # future, we might want to set a timeout on suspended process so we
    # need this information.
    suspension_date = fields.Date('Suspension Date')

    # This is an easy access field, as the data also exists in the session.
    for_user = fields.Many2One('res.user',
                               'Suspended by')

    # Process Description, computed at creation time from session data
    desc = fields.Char('Process Description')

    # Process Model :
    process_model_name = fields.Char('Process Model')

    # Data from the session
    session_data = fields.Text('Data')


class ResumeWizard(Wizard):
    '''
        This class is designed to provide an interface for restarting a
        suspended process.
    '''
    __name__ = 'ins_process.resume_process'
    start_state = 'action'

    class LaunchStateAction(StateAction):
        '''
            We need a special StateAction in which we will override the
            get_action method to calculate the name of the wizard we must
            launch
        '''

        def __init__(self):
            StateAction.__init__(self, None)

        def get_action(self):
            # First we need to be sure that we are working on a suspended
            # process.
            if Transaction().context.get('active_model') != \
                                            'ins_process.suspended_process':
                self.raise_user_error(
                                'Selected record is not a suspended process')

            SuspendedProcess = Pool().get('ins_process.suspended_process')

            # Then we look for the associated record. Note that if we had not
            # check the active_model, we might have found something which would
            # not have been right !
            try:
                susp_process = SuspendedProcess(
                    Transaction().context.get('active_id'))
            except KeyError:
                susp_process = None
                self.raise_user_error('Could not find a process to resume')

            # Then we look for an action wizard associated to the process_model
            # of the suspended process :
            Action = Pool().get('ir.action')
            ActionWizard = Pool().get('ir.action.wizard')
            good_wizard, = ActionWizard.search([
                    ('model', '=', 'ins_process.suspended_process'),
                    ('wiz_name', '=', susp_process.process_model_name)
                                             ])

            # Finally, we just return the instruction to start an action wizard
            # with the id we just found.
            return Action.get_action_values('ir.action.wizard',
                                            good_wizard.id)

    # The only state of our wizard process is this one.
    action = LaunchStateAction()

    # We need to specify this method as we want to update the context of the
    # wizard that is going to be launched with the data we were provided with.
    def do_action(self, action):
        return (action, {
                     'id': Transaction().context.get('active_id'),
                     'model': Transaction().context.get('active_model'),
                     'ids': Transaction().context.get('active_ids'),
                         })


#####################################################
# Here is an example of implementation of a process #
#####################################################

# This section has been moved in tests/test_process.py

###############################################################################
# Here is an example of default tryton wizard, performing a basic             #
# subscription process. We just removed the class instanciations of tryton to #
# avoid conflicts                                                             #
###############################################################################


class SubscriptionProcess(Wizard):
    '''
        This class defines the subscription process. It asks the user all that
        will be needed to finally create a contract.
    '''
    _name = 'ins_contract.subscription_process'

    # Defines the starting state (fixed attribute name)
    start_state = 'project'

    # This is a step of the process. It is defined as a StateView, with the
    # foolowing arguments :
    #    The name of the entity that defines the step (cf infra,
    #    class ProjectState)
    #    The name of the view which will be used to display the step. Careful,
    #    this name must start with trytonmodule_name, in our case
    #    'insurance_contract'.
    #    A list of buttons. A button is defined with its label,
    #    the state which must be called when pressed, and a reference to an
    #    image file, which is used for displaying.
    project = StateView('ins_contract.subscription_process.project',
                        'insurance_contract.project_view',
                        [Button('Cancel',
                                'end',
                                'tryton-cancel'),
                         Button('Next',
                                'option_selection',
                                'tryton-go-next')])
    option_selection = StateView(
                        'ins_contract.subscription_process.option_selection',
                        'insurance_contract.option_selection_view',
                        [Button('Cancel',
                                'end',
                                'tryton-cancel'),
                         Button('Previous',
                                'project',
                                'tryton-go-previous'),
                         Button('Complete',
                                'validate',
                                'tryton-ok'),
                         ])

    # Transition State allows us to define a state which will only compute the
    # following step name through the function transition_statename.
    validate = StateTransition()

    # This method will set default values for the 'project' state
    # Syntax : default_statename(self, session, fields)
    #     session => give access to all previous states
    #     fields  => list of attributes used in the state view.
    def default_project(self, session, fields):
        # In this particular case, all we want to do is set today's date as
        # the default value for the start_date field
        date = Pool().get('ir.date').today()
        return {'start_date': date}

    def default_option_selection(self, session, fields):
        # Here it is a little harder. We want to create a list of options
        # (more Coverage Diplayers than Options) which will be used as an
        # interface for the user.
        options = []

        # We have access to the product previously selected by the user
        # in the session.project (session.any_state_name) attribute
        for coverage in session.project.product.options:
            # We create a list of coverage_displayer, whose model is
            # calculated as it is specified in the definition of the
            # option field of coverage_displayer
            options.append({'for_coverage': coverage.id,
                            'from_date': max(coverage.start_date,
                                             session.project.start_date),
                           'status': 'active'})
        return {'options': options}

    # This function is automatically called when we click on the "next" step of
    # the option_selection state. We must return the name of the state which
    # must be called afterwards, but we also have a chance to work a little
    # before.
    def transition_validate(self, session):
        contract_obj = Pool().get('ins_contract.contract')
        options = []
        for option in session.option_selection.options:

            # We create a list of tuples ('create', dict), which will be passed
            # to the contract_obj.create method to gives it the data it needs
            # to create the options.
            options.append(('create',
                            {'start_date': option.from_date,
                             'coverage': option.for_coverage.id,
                             }))

        # Once the options are prepared, we can create the contract. To do so,
        # we use the create method from the contract_obj model, giving it a
        # dictionnary of attributes / values. For the options field, which is
        # a list, we give it the list of tuple we just created, which will
        # provide the create method with all the data it needs to create the
        # contract record.
        contract_obj.create({'options': options,
                             'product': session.project.product.id,
                             'start_date': session.project.start_date,
                             'contract_number': contract_obj.
                                                    get_new_contract_number()
                             })

        # We do not forget to return the name of the next step. 'end' is the
        # technical step marking the end of the process.
        return 'end'


class ProjectState(CoopView):
    _name = 'ins_contract.subscription_process.project'
    # We define the list of attributes which will be used for display
    start_date = fields.Date('Effective Date',
                                 required=True)
    product = fields.Many2One(
        'ins_product.product',
        'Product',
        domain=[('start_date', '<=', Eval('start_date'))],
        depends=['start_date', ],
        required=True)


class OptionSelectionState(CoopView):
    _name = 'ins_contract.subscription_process.option_selection'
    options = fields.Many2Many('ins_contract.coverage_displayer',
                               None,
                               None,
                               'Options Choices')
