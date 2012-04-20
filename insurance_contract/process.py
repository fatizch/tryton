# Needed for displaying objects
from trytond.model import ModelView
from trytond.model import fields as fields

# Needed for Wizardry
from trytond.wizard import Wizard, Button, StateView, StateTransition

# Needed for getting models
from trytond.pool import Pool

ACTIONS = ('go_previous', 'go_next', 'cancel', 'complete', 'check')


class ProcessState(ModelView):
    _name = 'ins_contract.process_state'

    cur_errors = fields.Text('Errors')
    cur_action = fields.Selection(
                    [(action, action) for action in list(ACTIONS)],
                    'Current Action')
    process_desc = fields.Many2One('ins_contract.process_desc',
                                   'Process Description')
    cur_step = fields.Char('Current step')
    cur_step_desc = fields.Many2One('ins_contract.step_desc',
                                    'Step Descriptor')

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

    # This is not a real state, it will only be used as a storage step for
    # the process' data
    process_state = StateView('ins_contract.process_state',
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

    steps_next = StateTransition()
    steps_previous = StateTransition()
    steps_cancel = StateTransition()
    steps_complete = StateTransition()
    steps_check = StateTransition()

    # We use the fact that we know the start step to set up a few things
    def transition_steps_start(self, session):
        process_desc_obj = Pool().get('ins_contract.process_desc')
        res, = process_desc_obj.search([
                            ('process_model', '=', self._name)],
                            limit=1)
        session.process_state.process_desc = res

        (step_obj, step_name) = process_desc_obj.get_first_step_desc(
                                            session.process_state.process_desc)
        for state in self.states:
            if (isinstance(self.states[state], StateView)
                and self.states[state].model_name == step_name):
                first_step = state
                break
        # We want to use the process_state's fields to store persistent data.
        session.process_state.cur_step = first_step
        session.process_state.cur_step_desc = step_obj.id
        return first_step

    @staticmethod
    def coop_process_name():
        return ''

    def get_state_from_model(self, step_model):
        for state in self.states:
            if (isinstance(self.states[state], StateView)
                and self.states[state].model_name == step_model):
                return self.states[state]

    def transition_master_step(self, session):
        process_desc_model = Pool().get('ins_contract.process_desc')
        cur_state_obj = self.states[session.process_state.cur_step]
        cur_state_model = Pool().get(cur_state_obj.model_name)
        cur_action = session.process_state.cur_action
        cur_step_desc = session.process_state.cur_step_desc
        cur_process_desc = session.process_state.process_desc

        data = {}

        if cur_action == 'check':
            (res, errors) = cur_state_model.check_step(session,
                                                       data,
                                                       cur_step_desc)
            if not res:
                self.raise_user_error('\n'.join(errors))
            return session.process_state.cur_step
        elif cur_action == 'cancel':
            return 'end'
        elif cur_action == 'complete':
            return 'end'
        elif cur_action == 'go_next':
            next_step_desc = process_desc_model.get_next_step(cur_step_desc,
                                            cur_process_desc)
            next_step_state = self.get_state_from_model(
                                            next_step_desc.step_model)
            next_state_model = Pool().get(next_step_state.model_name)
            res = next_state_model.check_step(session, data, next_step_desc)
            return ''
        return session.process_state.cur_step

    def transition_steps_next(self, session):
        session.process_state.cur_action = 'go_next'
        return 'master_step'

    def transition_steps_previous(self, session):
        session.process_state.cur_action = 'go_previous'
        return 'master_step'

    def transition_steps_cancel(self, session):
        session.process_state.cur_action = 'cancel'
        return 'master_step'

    def transition_steps_complete(self, session):
        session.process_state.cur_action = 'complete'
        return 'master_step'

    def transition_steps_check(self, session):
        session.process_state.cur_action = 'check'
        return 'master_step'

    def calculate_next_step(self, session, forstep, fromstep, action):
        '''
            This method is used to calculate the name of the next step to
            execute. It can call itself if needed.

            forstep is the step object where the action request was done.
            It is the state corresponding to the last displayed StateView
            fromstep is the current state object
            action is a process.ACTIONS value
        '''


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
    '''

    def button_next(self):
        return Button('Next',
                      'steps_next',
                      'tryton-go-next')

    def button_previous(self):
        return Button('Previous',
                      'steps_previous',
                      'tryton-go-previous')

    def button_cancel(self):
        return Button('Cancel',
                      'steps_cancel',
                      'tryton-cancel')

    def button_complete(self):
        return Button('Complete',
                      'steps_complete',
                      'tryton-ok')

    def button_check(self):
        return Button('Check',
                      'steps_check',
                      'tryton-help')

    def all_buttons(self):
        return [self.button_previous(),
                self.button_check(),
                self.button_next(),
                self.button_complete(),
                self.button_cancel()]


class CoopStateView(StateView, CoopState):
    '''
        This class is an extension of CoopState which will allow us to easily
        create step classes.

        To use, just create an instance with the name of the model and view,
        buttons will be calculated automatically.
    '''

    def __init__(self, name, view):
        super(CoopStateView, self).__init__(name,
                                        view,
                                        self.all_buttons())


class CoopStep(ModelView):
    @staticmethod
    def coop_step_name():
        return ''

    def get_methods_starting_with(self, prefix):
        return [getattr(self, method)
                   for method in dir(self)
                   if (callable(getattr(self, method))
                       and method.startswith(prefix))]

    def fill_data_dict(self, session, data, data_pattern):
        return {}

    def call_client_rules(self, session, rulekind, data, step_desc):
        step_desc_model = Pool().get('ins_contract.step_desc')
        method_desc_model = Pool().get('ins_contract.step_method_desc')
        for rule in step_desc_model.get_appliable_rules(step_desc, rulekind):
            needed_data = method_desc_model.get_data_pattern(rule)
            yield method_desc_model.calculate(rule,
                                        self.fill_data_dict(session,
                                                            data,
                                                            needed_data))

    def do_after(self, session, data, step_desc):
        pass

    def do_before(self, session, data, step_desc):
        pass

    def must_step_over(self, session, data, step_desc):
        methods = self.get_methods_starting_with('step_over_')
        (result, errors) = (False, [])
        for method in methods:
            (res, error) = method.__call__(session, data)
            if res:
                result = True
                errors += error
        for res, errs in self.call_client_rules(session,
                                                '0_step_over',
                                                data,
                                                step_desc):
            result = res
            errors += errs
        return (result, errors)

    def step_over(self, session, data, step_desc):
        pass

    def before_step(self, session, data, step_desc):
        pass

    def check_step(self, session, data, step_desc):
        methods = self.get_methods_starting_with('check_step_')
        (result, errors) = (True, [])
        for method in methods:
            (res, error) = method.__call__(session, data)
            if not res:
                result = False
                errors += error
        for res, errs in self.call_client_rules(session,
                                          '2_check_step',
                                          data,
                                          step_desc):
            result = result and res
            errors += errs
        return (result, errors)

    def post_step(self, session, data, step_desc):
        pass

    def check_step_schtroumpf_validation(self, session, data):
        return (False, ['Schtroumpf1'])


class DummyStep(CoopStep):
    _name = 'ins_contract.dummy_process.dummy_step'
    name = fields.Boolean('Name')

    @staticmethod
    def coop_step_name():
        return 'Dummy Step'

    def check_step_schtroumpf_validation(self, session, data):
        return (False, ['Schtroumpf'])

    def check_step_kiwi_validation(self, session, data):
        return (False, ['Kiwi'])

DummyStep()


class DummyStep1(CoopStep):
    _name = 'ins_contract.dummy_process.dummy_step1'
    name = fields.Boolean('Name')

    @staticmethod
    def coop_step_name():
        return 'Dummy Step 1'

    def check_step_schtroumpf_validation(self, session, data):
        return (False, ['Schtroumpf'])

    def check_step_kiwi_validation(self, session, data):
        return (False, ['Kiwi'])

DummyStep1()


class DummyProcess(CoopProcess):
    _name = 'ins_contract.dummy_process'

    dummy_step = CoopStateView('ins_contract.dummy_process.dummy_step',
                               'insurance_contract.dummy_view')
    dummy_step1 = CoopStateView('ins_contract.dummy_process.dummy_step1',
                               'insurance_contract.dummy_view')

    @staticmethod
    def coop_process_name():
        return 'Dummy Process Test'

DummyProcess()
