import datetime
import copy

# Needed for displaying objects
from trytond.model import ModelView, ModelSQL
from trytond.model import fields as fields

# Needed for Wizardry
from trytond.wizard import Wizard, Button, StateView, StateTransition
from trytond.wizard import StateAction, Session

# Needed for getting models
from trytond.pool import Pool

# Needed for resuming processes
from trytond.transaction import Transaction
from trytond.protocols.jsonrpc import JSONEncoder
from trytond.model.browse import BrowseRecordNull
from tools import AbstractObject, to_list

from trytond.pyson import Eval

# Needed for serializing data
try:
    import simplejson as json
except ImportError:
    import json

ACTIONS = ('go_previous', 'go_next', 'cancel', 'complete', 'check', 'suspend')


class MetaAbstract(type):
    def __new__(cls, name, bases, attrs):
        for (field_name, field_model) in attrs['__abstracts__']:
            attrs[field_name + '_db'] = fields.Many2One(field_model,
                                                        field_name)
            attrs[field_name + '_str'] = fields.Text('Json' + field_name)
        return super(MetaAbstract, cls).__new__(cls, name, bases, attrs)


class WithAbstract(object):

    __metaclass__ = MetaAbstract

    __abstracts__ = []

    @staticmethod
    def get_abstract_object(session, field_name):
        result = getattr(session.process_state, field_name + '_db')
        if isinstance(result, BrowseRecordNull):
            result = AbstractObject.load_from_text(
                        getattr(session.process_state, field_name + '_str'))
        else:
            result = AbstractObject(result._model._name, result.id)
        if result is None:
            result = AbstractObject(getattr(session.process_state._model,
                                            field_name + '_db').model_name)
        return result

    @staticmethod
    def save_abstract_object(session, field_name, for_object):
        setattr(session.process_state, field_name + '_str',
                AbstractObject.store_to_text(for_object))
        session.process_state.dirty = True

    @staticmethod
    def abstract_objs(session):
        res = []
        for field in [field for field in dir(session.process_state._model)
                                if field[-3:] == '_db']:
            res.append(field[:-3])
        return res

    @staticmethod
    def get_abstract_objects(session, fields):
        objs = WithAbstract.abstract_objs(session)
        elems = to_list(fields)
        res = []
        for field in elems:
            if field in objs:
                res += [WithAbstract.get_abstract_object(session, field)]
            else:
                res += [None]
        if type(fields) == list:
            return tuple(res)
        else:
            return res[0]

    @staticmethod
    def save_abstract_objects(session, fields):
        objs = WithAbstract.abstract_objs(session)
        for_list = to_list(fields)
        for field, value in for_list:
            if field in objs:
                WithAbstract.save_abstract_object(session, field, value)


class ProcessState(ModelView):
    '''
        This class is a fake step. Its only purpose is to provide us with a
        place to store all process-related persistent data.

        As we want something more dynamic than the default tryton wizards, we
        typically need to know where we are in the process and what we are
        doing. That's what this step is for.
    '''
    _name = 'ins_process.process_state'

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

    @staticmethod
    def add_error(session, error):
        errors = to_list(error)
        session.process_state.errors += '\n'.join(errors)

    @staticmethod
    def init_session(session):
        session.process_state.errors = ''
        for elem in set([elem for elem in dir(session.process_state._model)
                     if (elem[-3:] == '_db' or elem[-4:] == '_str')]):
            if not hasattr(session.process_state, elem + '_db'):
                setattr(session.process_state, elem + '_db', 0)
            if not hasattr(session.process_state, elem + '_str'):
                setattr(session.process_state, elem + '_str', '')
        session.on_product = 0

ProcessState()


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
    _name = 'ins_process.coop_process'

    # This is not a real state, it will only be used as a storage step for
    # the process' data
    process_state = StateView('ins_process.process_state',
                              '',
                              [])

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

    # We use the fact that we know the start step to set up a few things

    def resume_suspended(self, session):
        susp_process_obj = Pool().get('ins_process.suspended_process')
        try:
            susp_process = susp_process_obj.browse(
                                        Transaction().context.get('active_id'))
        except KeyError:
            susp_process = None

        # If a suspended process is found in the current context, resume it
        if not susp_process is None:
            # We get a dictionnary with the data from the stored session
            susp_data = json.loads(susp_process.session_data.encode('utf-8'))
            # Then update everything.
            for key, value in susp_data.iteritems():
                session.data[key].update(value)
                getattr(session, key).dirty = True
            session.process_state.from_susp_process = susp_process.id
            self.dirty = True

    def transition_steps_start(self, session):
        # We check if we are currently trying to resume a suspended process
        if (Transaction().context.get('active_model')
                            == 'ins_process.suspended_process'):
            self.resume_suspended(session)
            return session.process_state.cur_step

        # If not, we go on and start a new process
        # First of all, we get and set the process descriptor.
        process_desc_obj = Pool().get('ins_process.process_desc')
        try:
            res, = process_desc_obj.search([
                                        ('process_model', '=', self._name)],
                                           limit=1)
        except Exception:
            # If no process desc is found, we raise an error and exit the
            # process.
            res = None
        if res is None:
            self.raise_user_error('Could not find a process descriptor for %s,\
                                    \nplease contact software admin.'
                                    % self.coop_process_name())
            return 'end'
        session.process_state.process_desc = res

        ProcessState.init_session(session)

        # We then asks the process desc which one is the first step
        (step_obj, step_name) = process_desc_obj.get_first_step_desc(
                                            session.process_state.process_desc)

        # We use the answer to look for the associated state name (step_desc
        # associations are based on coop_step_name() calls)
        _, first_step_name = self.get_state_from_model(step_name)

        # We use the process_state's fields to store those persistent data :
        session.process_state.cur_step = first_step_name
        session.process_state.cur_step_desc = step_obj.id

        # Now the work begins : we get the step model
        state_model = Pool().get(step_obj.step_model)

        # And initialize the steps (exiting in case of errors)
        (res, errors) = state_model.do_before(session,
                                              step_obj)
        if not res:
            self.raise_user_error('Could not initialize process, exiting\n'
                                  + '\n'.join(errors))
            return 'end'

        # Time to display
        return first_step_name

    @staticmethod
    def coop_process_name():
        '''
            This method (static) is used as a label for the wizard, it is
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

    def transition_master_step(self, session):
        '''
            This method will be called every time a flow button is clicked.
            The transition_steps_* will set a few things in
            session.process_state (typically cur_action) so that we are
            able to know where we are in the process flow.
        '''
        # Being cautious, we store the current step name, as it will be
        # modified during calculation.
        from_step = session.process_state.cur_step

        # Now we call calculate_next_step, which will use the data
        # available in the session object to compute where we should go,
        # depending on where we currently are and the cur_action.
        res = self.calculate_next_step(session)

        # Just to be sure...
        if res == '':
            ProcessState.add_error(session, 'Could not calculate next step')
            res = from_step

        # We store the new state name (even though it should already be
        # done.
        session.process_state.cur_step = res

        # We get the errors
        errors = session.process_state.errors
        if len(errors) > 0:
            # If there are some, we clear them.
            session.process_state.errors = ''

            # We need to save again, as raise_user_errors drops the session
            session.save()

            # And we finally display them
            self.raise_user_error(errors)

        # and we save the session
        session.save()
        return res

    # Transition method, we just set cur_action for now, and call master_step
    def transition_steps_next(self, session):
        session.process_state.cur_action = 'go_next'
        return 'master_step'

    # Transition method, we just set cur_action for now, and call master_step
    def transition_steps_previous(self, session):
        session.process_state.cur_action = 'go_previous'
        return 'master_step'

    # Transition method, we just set cur_action for now, and call master_step
    def transition_steps_cancel(self, session):
        session.process_state.cur_action = 'cancel'
        return 'master_step'

    # Transition method, we just set cur_action for now, and call master_step
    def transition_steps_complete(self, session):
        session.process_state.cur_action = 'complete'
        return 'master_step'

    # Transition method, we just set cur_action for now, and call master_step
    def transition_steps_check(self, session):
        session.process_state.cur_action = 'check'
        return 'master_step'

    # Transition method, we just set cur_action for now, and call master_step
    def transition_steps_suspend(self, session):
        session.process_state.cur_action = 'suspend'
        return 'master_step'

    # This step will be called in case of soft termination (cancel or complete)
    # We need to delete the suspended_process object if it exists
    def transition_steps_terminate(self, session):
        tmp_id = session.process_state.from_susp_process
        if tmp_id > 0:
            susp_process_obj = Pool().get('ins_process.suspended_process')
            susp_process_obj.delete([tmp_id])
        return 'end'

    # This method will be called when clicking on the 'complete' button
    def do_complete(self, session):
        return (True, [])

    def calculate_next_step(self, session):
        '''
            This method is used to calculate the name of the next step to
            execute. It can call itself if needed.
        '''
        # We just need to get a few things at start:
        #    Process desc model, needed for calling methods
        process_desc_model = Pool().get('ins_process.process_desc')
        step_desc_model = Pool().get('ins_process.step_desc')
        #    Current state object (the CoopStateView object)
        cur_state_obj = self.states[session.process_state.cur_step]
        #    Current state model ('ins_process.process_name.step_name')
        cur_state_model = Pool().get(cur_state_obj.model_name)
        #    Current action : what do we want to do ?
        cur_action = session.process_state.cur_action
        #    Current step descriptor : a 'ins_process.step_desc' object
        #    whose step_model field would be cur_state_model
        cur_step_desc = session.process_state.cur_step_desc
        #    Current process descriptor : this one is already stored
        #    in session.process_state
        cur_process_desc = session.process_state.process_desc

        # Here we go : we switch case based on cur_action :
        if cur_action == 'check':
            # CHECK :
            # Well, just call check_step
            (res, errors) = cur_state_model.check_step(session,
                                                       cur_step_desc)
            # and save the result
            if not res:
                ProcessState.add_error(session, errors)
            else:
                ProcessState.add_error(session, 'Everything is OK')
            return session.process_state.cur_step
        elif cur_action == 'cancel':
            # CANCEL :
            # End of the process
            return 'steps_terminate'
        elif cur_action == 'complete':
            # COMPLETE :
            # First we try to complete the current step :
            (res, errors) = cur_state_model.do_after(session,
                                                       cur_step_desc)
            # If we cannot, we stay where we are
            if not res:
                ProcessState.add_error(session, errors)
                return session.process_state.cur_step

            # If we can, we call the do_complete method on the process
            (res, errors) = self.do_complete(session)
            # If it works, end of the process
            if res:
                return 'steps_terminate'
            # else, back to current step...
            ProcessState.add_error(session, errors)
            return session.process_state.cur_step
        elif cur_action == 'go_previous':
            # PREVIOUS :
            # We need to get the previous step from the process desc
            next_step_desc = process_desc_model.get_prev_step(cur_step_desc,
                                            cur_process_desc)
            # We go back until we got a non virtual step.
            while next_step_desc.virtual_step == True:
                next_step_desc = process_desc_model.get_prev_step(
                                            next_step_desc,
                                            cur_process_desc)
            # If it does not exist, no need to go further
            if next_step_desc == cur_step_desc:
                return session.process_state.cur_step
            # Now, we get our tools : step name, model, view
            (next_step_state, next_state_name) = self.get_state_from_model(
                                step_desc_model.get_step_model(
                                        next_step_desc,
                                        session.process_state.on_product))
            if next_step_state == '':
                ProcessState.add_error(session, 'Could not find step model')
                return ''
            next_state_model = Pool().get(next_step_state.model_name)

            # Should we display this step ?
            (res, errors) = next_state_model.must_step_over(session,
                                                            next_step_desc)

            if not res:
                # Yes => here we go (no need to call the before method, we do
                # not want to reset the step)
                session.process_state.cur_step = next_state_name
                session.process_state.cur_step_desc = next_step_desc.id
                return session.process_state.cur_step
            else:
                # No => ok, we just set this step as the current step, and
                # we go on.
                session.process_state.cur_step = next_state_name
                session.process_state.cur_step_desc = next_step_desc.id
                # (Here we suppose that the first step will never be stepped
                # over, we might have to change a few things if it happens to
                # be possible)
                return self.calculate_next_step(session)
        elif cur_action == 'go_next':
            # NEXT :
            # As for previous, we get the next step from the process desc
            next_step_desc = process_desc_model.get_next_step(cur_step_desc,
                                            cur_process_desc)
            # and we exit now if it does no exist
            if next_step_desc == cur_step_desc:
                return session.process_state.cur_step
            # First of all we go on until we find a non-virtual step
            while next_step_desc.virtual_step == True:
                result = False
                errors = []
                # We call the step_over methods
                for res, errs in CoopStepMethods.call_client_rules(
                                            session,
                                            default=False,
                                            client_rules='0_step_over'):
                    if res != False:
                        result = res
                        errors += errs
                # In case of error, we stop here then go back to the step
                if errors != []:
                    ProcessState.add_error(session, errors)
                    # A '' return value will make it so we stay on the
                    # current step
                    return ''
                if result == False:
                    # We must call the check methods :
                    result = True
                    errors = []
                    # We call the step_over methods
                    for res, errs in CoopStepMethods.call_client_rules(
                                            session,
                                            default=True,
                                            client_rules='2_check_step'):
                        if res != True:
                            result = res
                            errors += errs
                    if result == False:
                        ProcessState.add_error(session, errors)
                        return ''
                next_step_desc = process_desc_model.get_next_step(
                                                    next_step_desc,
                                                    cur_process_desc)
            # Now we are sure to have a non-virtual step, so we may go on...
            # We got our tools
            (next_step_state, next_state_name) = \
                    self.get_state_from_model(step_desc_model.get_step_model(
                                        next_step_desc,
                                        session.process_state.on_product))
            next_state_model = Pool().get(next_step_state.model_name)
            # And we try to finish the current step
            (res, errors) = cur_state_model.do_after(session,
                                                       cur_step_desc)
            if not res:
                # If it does not work, we stop here
                ProcessState.add_error(session, errors)
                return session.process_state.cur_step
            else:
                # If it works, we call the before of the next method
                (res, errors) = next_state_model.do_before(session,
                                                           next_step_desc)
                if not res:
                    # Again, it it does not work, we stop right here
                    ProcessState.add_error(session, errors)
                    return session.process_state.cur_step
                # Now we must check that the step should be displayed
                (res, errors) = next_state_model.must_step_over(session,
                                                            next_step_desc)
                # We set the step as the current step anyway
                session.process_state.cur_step = next_state_name
                session.process_state.cur_step_desc = next_step_desc.id
                if not res:
                    # We must not step over, it ends here
                    return session.process_state.cur_step
                else:
                    # We must step over, so we just calculate_next_step
                    # again. Note that it supposed that the last step will
                    # not be stepped over !
                    return self.calculate_next_step(session)
        elif cur_action == 'suspend':
            # SUSPEND :
            # We create or find a suspended process, then store the current
            # process session data in it.
            susp_process_obj = Pool().get('ins_process.suspended_process')
            data_dict = {
                         'suspension_date': datetime.date.today(),
                         'for_user': session._session._user,
                         'desc': '%s, step %s' % (self.coop_process_name(),
                                            cur_state_model.coop_step_name()),
                         'process_model_name': self._name,
                         # We need the session_data to be persistent in order
                         # to be able to resume the process in the same state
                         # as it was before, so we encode it in a json string.
                         'session_data': json.dumps(session.data,
                                                    cls=JSONEncoder)
                         }
            if session.process_state.from_susp_process > 0:
                # Already exist, we just need an update
                susp_process_obj.write(session.process_state.from_susp_process,
                                       data_dict)
            else:
                # Does not exist, create it !
                tmp_id = susp_process_obj.create(data_dict)
                if tmp_id is None:
                    self.raise_user_error('Could not store process !')
            return 'end'
        # Just in case...
        return session.process_state.cur_step

CoopProcess()


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
    def get_defaults(self, wizard, session, state_name, fields):
        res = {}
        # First we get the existing data for our step in the current session
        default_data = getattr(session, state_name)._data
        if default_data:
            # If it exists, we go through each field and set a new entry in the
            # return dict
            for field in [field for field in fields
                                if (field in default_data)]:
                res[field] = default_data[field]
        return res

    def get_buttons(self, wizard, state_name):
        buttons = super(CoopStateView, self).get_buttons(wizard,
                                                         state_name)
        process_desc_obj = Pool().get('ins_process.process_desc')
        process, = process_desc_obj.search([
                                        ('process_model', '=', wizard._name)],
                                           limit=1)
        res_buttons = []
        for step_desc in process_desc_obj.browse(process).steps:
            state_obj = Pool().get(self.model_name)
            if isinstance(state_obj, DependantState):
                if (not state_obj.depends_on_state() ==
                                                step_desc.product_step_name):
                    continue
            elif self.model_name != step_desc.step_model:
                continue
            default_button, _ = step_desc.button_default
            for button in buttons:
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

    def get_methods_starting_with(self, prefix):
        # This method is used to get all methods of the class that start with
        # the provided prefix
        return [getattr(self, method)
                   for method in dir(self)
                   if (callable(getattr(self, method))
                       and method.startswith(prefix))]

    @staticmethod
    def fill_data_dict(session, data_pattern):
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
    def call_client_rules(session, rulekind, step_desc):
        '''
            This method will look for and call the client defined ruler in the
            step_desc, which match the rulekind.
            It then asks the rule which data are needed for execution, fetchs
            the data and call the rule.

            It is intended to be use as an iterator which will yield the result
            of each call, which is a tuple containing the result and a list of
            errors.
        '''
        # We get the models
        step_desc_model = Pool().get('ins_process.step_desc')
        method_desc_model = Pool().get('ins_process.step_method_desc')

        # Then we iterate through the list of existing methods on the step_desc
        # which match our rule_kind
        for rule in step_desc_model.get_appliable_rules(step_desc, rulekind):
            # We get the needed data pattern for this method
            needed_data = method_desc_model.get_data_pattern(rule)
            # Then we call the fill_data_dict, feed its result to the
            # method, and yield the result
            yield method_desc_model.calculate(rule,
                            CoopStepMethods.fill_data_dict(session,
                                                            needed_data))

    def call_methods(self, session, step_desc, prefix, default=True,
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
        methods = self.get_methods_starting_with(prefix)
        (result, errors) = (default, [])
        # and execute each of them
        for method in methods:
            try:
                (res, error) = method.__call__(session)
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
                for res, errs in CoopStepMethods.call_client_rules(
                                                                session,
                                                                client_rules,
                                                                step_desc):
                    if res != default:
                        result = res
                        errors += errs
        return (result, errors)

    def do_after(self, session, step_desc):
        '''
            This method executes what must be done after clicking on 'Next'
            on the step's view. It will first check for errors then, if
            everything is ok, will go through post_step methods.

            It is designed as to avoid to be instance dependant, that is it
            should be possible to call it through a batch to simulate for
            instance a manual subscription.
        '''
        # Check for errors in current view
        (res, check_errors) = self.check_step(session, step_desc)
        post_errors = []
        if res:
            # If there are errors, there is no need (and it would be dangerous)
            # to continue
            (res, post_errors) = self.post_step(session, step_desc)
        return (res, check_errors + post_errors)

    def do_before(self, session, step_desc):
        '''
            This method executes what must be done before displaying the step
            view. It might be initializing values, creating objects for
            displaying, etc... It should also check that everything which will
            be necessary for the step completion is available in the session.

            It is designed as to avoid to be instance dependant, that is it
            should be possible to call it through a batch to simulate for
            instance a manual subscription.
        '''
        (res, errors) = self.before_step(session, step_desc)
        return (res, errors)

    def must_step_over(self, session, step_desc):
        '''
            This method calculates whether it is necessary to display the
            current step view.

            It is designed as to avoid to be instance dependant, that is it
            should be possible to call it through a batch to simulate for
            instance a manual subscription.
        '''
        (res, errors) = self.step_over(session, step_desc)
        return (res, errors)

    def step_over(self, session, step_desc):
        # This is the actual call to the step_over_ methods and client rules
        return self.call_methods(session,
                                 step_desc,
                                 'step_over_',
                                 default=False,
                                 client_rules='0_step_over')

    def before_step(self, session, step_desc):
        # This is the actual call to the before_step_ methods
        return self.call_methods(session,
                                 step_desc,
                                 'before_step_')

    def check_step(self, session, step_desc):
        # This is the actual call to the check_step_ methods and client rules
        return self.call_methods(session,
                                 step_desc,
                                 'check_step_',
                                 client_rules='2_check_step')

    def post_step(self, session, step_desc):
        # This is the actual call to the post_step_ methods
        return self.call_methods(session,
                                 step_desc,
                                 'post_step_')


class NoSessionFoundException(Exception):
    pass


class CoopView(ModelView):
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
            session_obj = Pool().get('ir.session.wizard')
            session = session_obj.browse(
                                    Transaction().context.get('from_session'))
            data = json.loads(session.data.encode('utf-8'))
            process_obj = Pool().get('ins_process.process_desc')
            wizard_obj = Pool().get(process_obj.browse(
                        data['process_state']['process_desc']).process_model,
                                    type='wizard')
            the_session = Session(wizard_obj,
                                  Transaction().context.get('from_session'))
            # session.data = data
            return the_session
        raise NoSessionFoundException

class CoopStep(ModelView, CoopStepMethods):
    def __init__(self):
        super(CoopStep, self).__init__()
        for field_name, field in self._columns.iteritems():
            if hasattr(field, 'context') and isinstance(field,
                                                        fields.One2Many):
                cur_attr = getattr(self, field_name)
                if cur_attr.context is None:
                    cur_attr.context = {}
                cur_attr.context['from_session'] = Eval('session_id')
                setattr(self, field_name, copy.copy(cur_attr))
        self._reset_columns()

    # Warning : to work, this field must be added to the view that will be used
    # displaying the Step, even though it is invisible.
    session_id = fields.Integer('Session Id',
                                states={'invisible': True})


class DependantState(CoopStep):
    def __init__(self):
        super(DependantState, self).__init__()

        def before_step_session_init(session):
            getattr(session,
                    self.__class__.state_name()
                    ).session_id = session._session.id
            return (True, [])
        setattr(self, 'before_step_session_init', before_step_session_init)

    @staticmethod
    def depends_on_state():
        pass

    @staticmethod
    def state_name():
        pass


class SuspendedProcess(ModelSQL, ModelView):
    '''
        This class represents a suspended process, which can be resumed later.
    '''
    _name = 'ins_process.suspended_process'

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

SuspendedProcess()


class ResumeWizard(Wizard):
    '''
        This class is designed to provide an interface for restarting a
        suspended process.
    '''
    _name = 'ins_process.resume_process'
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

            susp_process_obj = Pool().get('ins_process.suspended_process')

            # Then we look for the associated record. Note that if we had not
            # check the active_model, we might have found something which would
            # not have been right !
            try:
                susp_process = susp_process_obj.browse(
                                        Transaction().context.get('active_id'))
            except KeyError:
                susp_process = None
                self.raise_user_error('Could not find a process to resume')

            # Then we look for an action wizard associated to the process_model
            # of the suspended process :
            action_obj = Pool().get('ir.action')
            act_wizard_obj = Pool().get('ir.action.wizard')
            good_id = act_wizard_obj.search([
                        ('model', '=', 'ins_process.suspended_process'),
                        ('wiz_name', '=', susp_process.process_model_name)
                                             ])[0]

            # Finally, we just return the instruction to start an action wizard
            # with the id we just found.
            return action_obj.get_action_values('ir.action.wizard',
                good_id)

    # The only state of our wizard process is this one.
    action = LaunchStateAction()
    dummy_step = CoopStateView('ins_process.dummy_process.dummy_step',
                               # Remember, the view name must start with the
                               # tryton module name !
                               'insurance_process.dummy_view')

    # We need to specify this method as we want to update the context of the
    # wizard that is going to be launched with the data we were provided with.
    def do_action(self, session, action):
        return (action, {
                     'id': Transaction().context.get('active_id'),
                     'model': Transaction().context.get('active_model'),
                     'ids': Transaction().context.get('active_ids'),
                         })

    def transition_action(self, session):
        return 'dummy_step'

ResumeWizard()

#####################################################
# Here is an example of implementation of a process #
#####################################################


class DummyObject(ModelSQL, ModelView):
    _name = 'ins_process.dummy_object'
    contract_number = fields.Char('Contract Number')

DummyObject()


class DummyStep(CoopStep):
    # This is a step. It inherits from CoopStep, and has one attribute (name).
    _name = 'ins_process.dummy_process.dummy_step'
    name = fields.Char('Name')

    # This is its user-friendly name for creating the step desc
    @staticmethod
    def coop_step_name():
        return 'Dummy Step'

    # This is a before method, which will be useful to initialize our name
    # field. If we had a One2Many field, we could create objects and use their
    # fields to compute the default value of another.
    def before_step_init(self, session):
        session.dummy_step.name = 'Toto'
        return (True, [])

    # Those are validation methods which will be called by the check_step
    # method.
    # DO NOT FORGET to always return something
    def check_step_schtroumpf_validation(self, session):
        if session.dummy_step.name == 'Toto':
            return (False, ['Schtroumpf'])
        return (True, [])

    def check_step_kiwi_validation(self, session):
        if session.dummy_step.name == 'Toto':
            return (False, ['Kiwi'])
        return (True, [])

    def check_step_abstract_obj(self, session):
        if 'for_contract' in WithAbstract.abstract_objs(session):
            contract = WithAbstract.get_abstract_objects(session,
                                                        'for_contract')
            if contract.contract_number == 'Test':
                contract.contract_number = 'Toto'
            else:
                contract.contract_number = 'Test'
            WithAbstract.save_abstract_objects(session,
                                              ('for_contract', contract))
            return (True, [])
        else:
            return (False, ['Could not find for_contract'])

DummyStep()


class DummyStep1(CoopStep):
    # This is another dummy step
    _name = 'ins_process.dummy_process.dummy_step1'
    name = fields.Char('Name')

    # We initialize this step with some data from the previous step
    def before_step_init(self, session):
        # We cannot be sure that the current process uses a 'dummy_step',
        # so we test for one.
        # We also could make the state mandatory with else return (False, [..])
        if hasattr(session, 'dummy_step'):
            session.dummy_step1.name = session.dummy_step.name
        return (True, [])

    def check_step_abstract(self, session):
        for_contract, for_contract1 = WithAbstract.get_abstract_objects(
                                                        session,
                                                        ['for_contract',
                                                         'for_contract1'])
        for_contract1.contract_number = for_contract.contract_number
        WithAbstract.save_abstract_objects(session, ('for_contract1',
                                                     for_contract1))
        return (False, [session.process_state.for_contract_str,
                        session.process_state.for_contract1_str])

    @staticmethod
    def coop_step_name():
        return 'Dummy Step 1'

DummyStep1()


class DummyProcessState(ProcessState, WithAbstract):
    _name = 'ins_process.dummy_process_state'
    __abstracts__ = [('for_contract', 'ins_process.dummy_object'),
                     ('for_contract1', 'ins_process.dummy_object'),
                     ]

DummyProcessState()


class DummyProcess(CoopProcess):
    # This is a Process. It inherits of CoopProcess.
    _name = 'ins_process.dummy_process'

    process_state = StateView('ins_process.dummy_process_state',
                              '',
                              [])

    # We just need to declare the two steps
    dummy_step = CoopStateView('ins_process.dummy_process.dummy_step',
                               # Remember, the view name must start with the
                               # tryton module name !
                               'insurance_process.dummy_view')
    dummy_step1 = CoopStateView('ins_process.dummy_process.dummy_step1',
                               'insurance_process.dummy_view')

    # and give it a name.
    @staticmethod
    def coop_process_name():
        return 'Dummy Process Test'

    def do_complete(self, session):
        # Create and store stuff
        return (True, [])

DummyProcess()

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
        return {'start_date': datetime.date.today()}

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
                           'status': 'Active'})
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


class ProjectState(ModelView):
    _name = 'ins_contract.subscription_process.project'
    # We define the list of attributes which will be used for display
    start_date = fields.Date('Effective Date',
                                 required=True)
    product = fields.Many2One('ins_product.product',
                              'Product',
                              #domain=[('start_date',
                              #         '<=',
                              #         Eval('start_date'))],
                              depends=['start_date', ],
                              required=True)


class OptionSelectionState(ModelView):
    _name = 'ins_contract.subscription_process.option_selection'
    options = fields.Many2Many('ins_contract.coverage_displayer',
                               None,
                               None,
                               'Options Choices')

