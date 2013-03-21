from trytond.pool import PoolMeta, Pool
from trytond.rpc import RPC
from trytond.model.model import ModelMeta
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.model import fields

from trytond.modules.coop_utils import utils

try:
    import simplejson as json
except ImportError:
    import json


__all__ = [
    'Model',
    'ProcessFramework',
    'ClassAttr',
]


class AllowRPCDict(dict):
    '''
        This class allows us to replace the behaviour of the dictionnary
        used to manage the the RPC authorizations on the client.
    '''

    def __init__(self, allowed_prefix, previous_dict):
        # We need to override the init in order to store the prefix which
        # will later be used as a filter.
        # We also need to keep the previous values intact in the new structure
        super(AllowRPCDict, self).__init__()
        self.allowed_prefix = allowed_prefix
        self.update(previous_dict)

    def __getitem__(self, name):
        # When used to decide whether a given method is available for distant
        # calling, it first checks that its name does not start with the
        # prefix given when created.
        if name.startswith(self.allowed_prefix):
            return RPC(instantiate=0, readonly=False)
        return super(AllowRPCDict, self).__getitem__(name)

    def __contains__(self, name):
        # Any name starting with the allowed prefix is allowed !
        if name.startswith(self.allowed_prefix):
            return True
        return super(AllowRPCDict, self).__contains__(name)


class DynamicButtonDict(dict):
    '''
        The purpose of this class is to provide a way to use db defined
        states for the generic buttons of the class.
    '''

    def __init__(self, allowed_prefix, previous_dict, for_class):
        # This class must be initialized with the prefix that will be used to
        # distinguish generic methods from everything else.
        super(DynamicButtonDict, self).__init__()
        self.allowed_prefix = allowed_prefix
        self.update(previous_dict)
        self.for_class = for_class

    def __getitem__(self, name):
        # If the name does not match the specified prefix, business as usual !
        if not name.startswith(self.allowed_prefix):
            return super(AllowRPCDict, self).__getitem__(name)

        # Remove the prefix before going forward
        button_data = name[len(self.allowed_prefix):].split('_')

        return self.for_class.calculate_button_states(button_data)

    def __contains__(self, name):
        # Names starting sith the allowed prefix are in, no matter what !
        if name.startswith(self.allowed_prefix):
            return True
        return super(AllowRPCDict, self).__contains__(name)


class ClassAttr(ModelMeta):
    '''
        The purpose of this class is to allow us to override the __getattr__
        of the class it instanciate in order to be able to direct all the calls
        to the 'generic' buttons toward a generic method for dispatching.
    '''

    def __init__(self, name, bases, dct):
        self.allowed_buttons = dct.get('__allowed_buttons__', None)
        super(ClassAttr, self).__init__(name, bases, dct)

    def __getattr__(self, name):
        # If we are looking for a method which matches the prefix,
        if self.__allowed_buttons__ and name.startswith(
                self.__allowed_buttons__):
            name = name[len(self.__allowed_buttons__):]
            # We return the methods computed with the generic method.
            return self.default_button_method(name)
        return super(ClassAttr, self).__getattr__(name)


class Model():
    'Model'
    '''
        We need to override the Model Class in order to add the is_workflow
        field so we can find which classes are workflow compatible.
    '''

    __metaclass__ = PoolMeta
    __name__ = 'ir.model'

    is_workflow = fields.Boolean('Is Workflow')


class ProcessFramework(Model):
    'Process Framework'

    __metaclass__ = ClassAttr

    # We set the prefix for our buttons
    __allowed_buttons__ = '_button_'

    __name__ = 'process.process_framework'

    # The current state is used to store which process is currently being
    # executed and which step is the current step
    current_state = fields.Many2One(
        'process.process_step_relation',
        'Current State',
        ondelete='RESTRICT', states={'readonly': True})

    @classmethod
    def __setup__(cls):
        super(ProcessFramework, cls).__setup__()

        # We prepare the class to respond to generated buttons
        cls.__rpc__ = AllowRPCDict(cls.__allowed_buttons__, cls.__rpc__)

        # We also need to plug in a way to properly set the states for
        # thsoe buttons
        cls._buttons = DynamicButtonDict(
            cls.__allowed_buttons__, cls._buttons, cls)

        # The Error you want to see !
        cls._error_messages.update(
            {
                'everything_ok': 'Everything is good !'
            })

    @classmethod
    def __register__(cls, module_name):
        # We need to define the fact that this class is a Workflow class in the
        # database.
        super(ProcessFramework, cls).__register__(module_name)

        GoodModel = Pool().get('ir.model')

        good_model, = GoodModel.search([
            ('model', '=', cls.__name__)], limit=1)

        # Basically, that is just setting 'is_workflow' to True
        good_model.is_workflow = True

        good_model.save()

    @classmethod
    def build_instruction_transition_method(cls, process, transition):
        def button_transition_generic(works):
            # Pretty straightforward : we find the matching transition
            StepTransition = Pool().get('process.step_transition')
            good_trans = StepTransition(int(transition[0]))

            for work in works:
                # Then execute it on each instance
                good_trans.execute(work)

                # Do not forget to save !
                work.save()

        return button_transition_generic

    @classmethod
    def default_button_method(cls, button_name):
        def void(works):
            return

        button_data = button_name.split('_')
        if not button_data:
            return void

        # The pattern for the transition is as follow :
        #      <instruction>_<process_desc_id>(_<data>)
        instruction = button_data[0]
        ProcessDesc = Pool().get('process.process_desc')
        process = ProcessDesc(button_data[1])

        try:
            return getattr(cls, 'build_instruction_%s_method' % instruction)(
                process, button_data[2:])
        except AttributeError:
            return void

    def set_state(self, value, process_name=None):
        # Setting the state means updating the current_state attribute
        if value is None:
            self.current_state = None
            return

        # To do that, we need to know the process on which we are working.
        # Either it is a parameter of the setter, either we look for it in the
        # current context
        if not process_name:
            process_name = Transaction().context.get('running_process')

        if not process_name and self.current_state:
            # We calculate it from the current_state
            process_desc = self.current_state.process
        else:
            ProcessDesc = Pool().get('process.process_desc')
            process_desc, = ProcessDesc.search([
                ('technical_name', '=', process_name),
            ], limit=1)

        self.current_state = process_desc.get_step_relation(value)

    @classmethod
    def default_current_state(cls):
        # When we are first accessing the record, if we are in a process, we
        # need to get a default value so that the states work properly
        process_name = Transaction().context.get('running_process')

        # Of course, no proces means no need
        if not process_name:
            return

        ProcessDesc = Pool().get('process.process_desc')

        process_desc, = ProcessDesc.search([
            ('technical_name', '=', process_name),
        ], limit=1)

        # The good value is the name associated to the first step of the
        # current process
        return process_desc.get_first_state_relation().id

    def get_rec_name(self, name):
        # We append the current_state to the record name
        res = super(ProcessFramework, self).get_rec_name(name)

        if res and self.current_state:
            return res + ' - ' + self.current_state.get_rec_name(name)

        return res

    @classmethod
    def raise_user_error(cls, errors, error_args=None,
                         error_description='', error_description_args=None,
                         raise_exception=True):
        if error_args or error_description or error_description_args:
            super(ProcessFramework, cls).raise_user_error(
                errors, error_args, error_description, error_description_args,
                raise_exception)
            return

        # We need a custom user error management as the displaying of errors
        # will be delayed in order to display several errors at one time.
        Translation = Pool().get('ir.translation')
        result = []

        # One error looks like : (error_code, (error_arg1, error_arg2))
        for the_error in errors:
            # TODO : Remove this cast which exists only for backward
            # compatibility
            if isinstance(the_error, (str, unicode)):
                error = the_error
                error_args = error_args
            else:
                error, error_args = the_error

            # We get the error code from the cls definition
            error = cls._error_messages.get(error, error)

            # We translate it if possible
            language = Transaction().language
            res = Translation.get_source(
                cls.__name__, 'error', language, error)
            if not res:
                res = Translation.get_source(error, 'error', language)
            if res:
                error = res

            # Then we apply the arguments
            try:
                error = error % error_args
            except TypeError:
                pass

            result.append(error)

        # We display the resulting list of strings
        # super(ProcessFramework, cls).raise_user_error('\n'.join(result))
        raise UserError('\n'.join(result))

    def button_is_active(self, button_name):
        good_button = self._buttons[button_name]
        if good_button is None:
            return False
        if good_button == {}:
            return True
        return not(
            'readonly' in good_button and
            utils.pyson_result(good_button['readonly'], self, evaled=True) or
            'invisible' in good_button and
            utils.pyson_result(good_button['invisible'], self, evaled=True))

    def is_button_available(self, process, executable):
        if executable.__name__ == 'process.step_desc':
            button_name = '_button_step_%s_%s' % (process.id, executable.id)
        elif executable.__name__ == 'process.step_transition':
            button_name = '_button_transition_%s_%s' % (
                process.id, executable.id)
        return self.button_is_active(button_name)

    @classmethod
    def button_transition_states(cls, process, transition_data):
        transition_id = int(transition_data[0])

        # We need to find the transition which matches the id given
        # through the name of the method.
        TransitionDesc = Pool().get('process.step_transition')
        good_transition = TransitionDesc(transition_id)

        # We need to manage the authroizations on the transition
        auth_pyson = good_transition.get_pyson_authorizations()

        # We get the transitions readonly pyson
        ro_pyson = good_transition.get_pyson_readonly()

        # To get the good pyson, we combine everything.
        res = '(%s) and (%s)' % (auth_pyson, ro_pyson)

        states = {}

        if res:
            states['readonly'] = utils.pyson_encode(res, True)

        return states

    @classmethod
    def button_currentstate_states(cls, transition_id):
        return {'readonly': True}

    @classmethod
    def calculate_button_states(cls, button_data):
        # If there is nothing, too bad
        if not button_data:
            return {'readonly': True}

        # The pattern for the transition is as follow :
        #      <instruction>_<process_desc_id>(_<data>)
        instruction = button_data[0]
        ProcessDesc = Pool().get('process.process_desc')
        process = ProcessDesc(button_data[1])

        try:
            return getattr(cls, 'button_%s_states' % instruction)(
                process, button_data[2:])
        except AttributeError:
            return {'readonly': True}
