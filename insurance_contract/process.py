import datetime

# Needed for displaying objects
from trytond.model import ModelView
from trytond.model import fields as fields

# Needed for Wizardry
from trytond.wizard import Wizard, Button, StateView, StateTransition

# Needed for Eval
from trytond.pyson import Eval

# Needed for getting models
from trytond.pool import Pool


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

    # Starting step, will be the same for all processes
    start_state = 'steps_start'

    # steps_start is a virtual step. So we just define it as a transition state
    # so that the transition_steps_start can be overriden in child classes.
    steps_start = StateTransition()

    # This step is the most important of all. It is the one that will manage
    # the execution flow through the use of session.process_data[cur_step] to
    # get the current step, and calls to CoopStep submethods.
    master_step = StateTransition()

    # We use the fact that we know the start step to set a few things in its
    # default method
    def default_steps_start(self, session, fields):
        # We want to use the session fields to store persistent data.
        process = {'cur_step': 'start_step'}
        session.process_data = process

    # Will be overriden in child classes
    def transition_steps_start(self, session):
        return 'master_step'

    def transition_master_step(self, session):
        # First we need to know where we are
        cur_step = session.process_data['cur_step']
        the_state = self.states[cur_step]
        state_model = Pool().get(the_state.model_name)

        if isinstance(the_state, CoopState):
            pass

CoopProcess()


class CoopState(object):
    '''
        This class is going to be use as a parent for all step classes.

        It defines :
            - a step_over method, which will be called to decide if the step
            should be displayed or stepped over
            - a before_step method, which is the code that must be executed
            before displaying the step
            - a check_step method, which will be called in order to check
            data consistency
            - a post_step method, which will be called if the user clicks on
            the next button, and if the check_step method returns 'True'

        To use, just create an instance with the name of the model and view,
        buttons will be calculated automatically.
    '''

    def step_over(self, session):
        pass

    def before_step(self, session):
        pass

    def check_step(self, session):
        pass

    def post_step(self, session):
        pass
