from trytond.pool import PoolMeta, Pool
from trytond.rpc import RPC
from trytond.model.model import ModelMeta

from trytond.tools import safe_eval

from trytond.pyson import Eval, PYSONEncoder, CONTEXT

from trytond.transaction import Transaction

from trytond.exceptions import UserError

try:
    import simplejson as json
except ImportError:
    import json

from trytond.model import fields
from trytond.model import ModelView


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

    def __init__(self, allowed_prefix, previous_dict):
        # This class must be initialized with the prefix that will be used to
        # distinguish generic methods from everything else.
        super(DynamicButtonDict, self).__init__()
        self.allowed_prefix = allowed_prefix
        self.update(previous_dict)

    def __getitem__(self, name):
        # If the name does not match the specified prefix, business as usual !
        if not name.startswith(self.allowed_prefix):
            return super(AllowRPCDict, self).__getitem__(name)

        # The 'name' is supposed to be the encoded id of the transition
        transition_id = name[len(self.allowed_prefix):].split('_')

        # If there is nothing, there is a problem
        if not transition_id:
            raise Exception

        # If there is only one, the button is just here for aesthetics, set it
        # to readonly !
        if len(transition_id) > 1:
            return {'readonly': True}

        # Now we need to find the transition which matches the id given
        # through the name of the method.
        TransitionDesc = Pool().get('process.step_transition')
        good_transition = TransitionDesc(transition_id[0])

        # We need to manage the authroizations on the transition
        auth_ids = map(lambda x: x.id, good_transition.authorizations)

        # So we build the corresponding pyson
        if auth_ids:
            auth_pyson = Eval('groups', []).contains(auth_ids)
        else:
            auth_pyson = True

        # We also got to take into account the custom pyson
        if not good_transition.pyson:
            pyson = False
        else:
            pyson = good_transition.pyson

        # To get the good pyson, we combine everything.
        res = None
        if auth_ids:
            res = auth_pyson
            if good_transition.pyson:
                res = res and pyson
        elif good_transition.pyson:
            res = pyson

        states = {}

        if good_transition.is_readonly:
            states['readonly'] = True

        if res:
            encoder = PYSONEncoder()
            res = encoder.encode(safe_eval(res, CONTEXT))
            states['invisible'] = res

        return states

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

    is_workflow = fields.Boolean(
        'Is Workflow',
    )


class ProcessFramework(ModelView):
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
    )

    @classmethod
    def __setup__(cls):
        super(ProcessFramework, cls).__setup__()

        # We need to set the fact that this model supports the framework
        cls.is_workflow = True

        # We prepare the class to respond to generated buttons
        cls.__rpc__ = AllowRPCDict(cls.__allowed_buttons__, cls.__rpc__)

        # We also need to plug in a way to properly set the states for
        # thsoe buttons
        cls._buttons = DynamicButtonDict(cls.__allowed_buttons__, cls._buttons)

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
    def default_button_method(cls, button_name):
        # button_name should be the transition's id
        transition, = map(int, button_name.split('_'))

        # This is the method that will be called when clicking on the button
        def button_generic(works):
            # Pretty straightforward : we find the matching transition
            StepTransition = Pool().get('process.step_transition')
            good_trans = StepTransition(transition)

            for work in works:
                # Then execute it on each instance
                good_trans.execute(work)

                # Do not forget to save !
                print '#' * 80
                print '%s' % work.current_state
                work.save()

        return button_generic

    def set_state(self, value, process_name=None):
        # Setting the state means updating the current_state attribute

        # To do that, we need to know the process on which we are working.
        # Either it is a parameter of the setter, either we look for it in the
        # current context
        if not process_name:
            process_name = Transaction().context.get('running_process')
            if not process_name:
                return

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

        if res:
            return res + ' - ' + self.current_state.get_rec_name(name)

        return self.current_state.get_rec_name(name)

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
                error_args = ()
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
        #super(ProcessFramework, cls).raise_user_error('\n'.join(result))
        raise UserError('\n'.join(result))
