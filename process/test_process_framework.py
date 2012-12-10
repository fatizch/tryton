from trytond.pool import PoolMeta, Pool
from trytond.rpc import RPC
from trytond.model import ModelMeta

from trytond.pyson import Eval

from trytond.transaction import Transaction

try:
    import simplejson as json
except ImportError:
    import json

from trytond.model import fields
from trytond.model import ModelView, ModelSQL


__all__ = [
    'Model',
    'ProcessFramework',
    'DemoProcess',
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

        # The 'name' is supposed to be the encoded ids of the steps which
        # define the transition
        from_id, to_id, = name[len(self.allowed_prefix):].split('_')

        # If they do not, there is a problem
        if not (from_id and to_id):
            raise Exception

        # If they are the same, the button is just here for aesthetics, set it
        # to readonly !
        if from_id == to_id:
            return {'readonly': True}

        # Now we need to find the transition which matches the ids given
        # through the name of the method.
        TransitionDesc = Pool().get('process.step_transition')
        try:
            good_transition, = TransitionDesc.search([
                    ('from_step', '=', int(from_id)),
                    ('to_step', '=', int(to_id)),
                ], limit=1)
        except:
            # If no transition matches, there is a problem
            raise

        # We need to manage the authroizations on the transition
        auth_ids = map(lambda x: x.id, good_transition.authorizations)

        # So we build the corresponding pyson
        if auth_ids:
            auth_pyson = Eval('groups', []).contains(auth_ids)
        else:
            auth_pyson = None

        # We also got to take into account the custom pyson
        pyson = good_transition.pyson

        # To get the good pyson, we combine everything.
        res = None
        if auth_ids:
            res = auth_pyson
            if pyson:
                res = res and pyson
        elif pyson:
            res = pyson

        if not res:
            return {}
        else:
            return {'invisible': res}

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
        raise AttributeError(name)


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

    #This field will be used to store the current_state for each process which
    #has been launched on this object so far.
    #It will be used as a storage field ofr en encoded json dictionnary
    process_state = fields.Char(
        'Process State',
    )

    # The process_state field is nice, but it is not usable 'as is'. The
    # cur_state field calculates the current state value depending on the
    # process currently executed.
    cur_state = fields.Function(
        fields.Char(
            'Current State',
            states={
                'invisible': True
            },
        ),
        'get_cur_state',
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
        # button_name should look like :
        #      id from + _ + id to
        from_step, to_step = map(int, button_name.split('_'))

        # This is the method that will be called when clicking on the button
        def button_generic(works):
            # Pretty straightforward : we find the matching transition
            StepTransition = Pool().get('process.step_transition')

            try:
                good_trans, = StepTransition.search([
                        ('from_step', '=', from_step),
                        ('to_step', '=', to_step),
                    ], limit=1)
            except ValueError:
                return

            for work in works:
                # Then execute it on each instance
                good_trans.execute(work)

                # Do not forget to save !
                work.save()

        return button_generic

    def set_state(self, value, process_name=None):
        # Setting the state means updating the dictionnary encoded in the
        # process_state field.

        # To do that, we need to know the process on which we are working.
        # Either it is a parameter of the setter, either we look for it in the
        # current context
        if not process_name:
            process_name = Transaction().context.get('running_process')
            if not process_name:
                return
        
        # Now we get the current states if it exists, create it if it does not
        if not (hasattr(self, 'process_state') and self.process_state):
            cur_state = {}
        else:
            cur_state = json.loads(self.process_state)

        # Set the value
        cur_state[process_name] = value

        # Then 'save' it in the process_state field
        self.process_state = json.dumps(cur_state)

    def get_state(self, process_name=None):
        # The current state dpends on the process we are working on. Either it
        # is provided as an argument, either we fetch it in the context
        if not process_name:
            process_name = Transaction().context.get('running_process')
            if not process_name:
                return ''
        
        # If no process_state is set (i.e. no process has ever been launched
        # on the current instance), there is no state to get
        if not (hasattr(self, 'process_state') and self.process_state):
            return ''

        # We load the process_state
        cur_state_dict = json.loads(self.process_state)

        # If the current process key does not exists, it means that it has
        # never been launched on the instance.
        # As we are in a process context, we assume that we want the first
        # step's name
        if not process_name in cur_state_dict:
            return self.default_cur_state()

        # Else, we return the value we found in the proces_state field.
        return cur_state_dict[process_name]

    def get_cur_state(self, name):
        # Just forward the request to the get_state method
        return self.get_state()

    @classmethod
    def default_cur_state(cls):
        # When we are first accessing the record, if we are in a process, we
        # need to get a default value so that the states work properly
        process_name = Transaction().context.get('running_process')

        # Of course, no proces means no need
        if not process_name:
            return ''

        ProcessDesc = Pool().get('process.process_desc')

        process_desc, = ProcessDesc.search([
                ('technical_name', '=', process_name),
            ], limit=1)

        # The good value is the name associated to the first step of the
        # current process
        return process_desc.first_step.technical_name

    def get_rec_name(self, name):
        # We append the current_state to the record name
        res = super(ProcessFramework, self).get_rec_name(name)

        if res:
            return res + ' - ' + self.get_cur_state(name)

        return self.get_cur_state(name)

    @classmethod
    def raise_user_error(cls, errors):
        # We need a custom user error management as the displaying of errors
        # will be delayed in order to display several errors at one time.
        Translation = Pool().get('ir.translation')
        result = []

        # One error looks like : (error_code, (error_arg1, error_arg2))
        for error, error_args in errors:
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
        super(ProcessFramework, cls).raise_user_error('\n'.join(result))
