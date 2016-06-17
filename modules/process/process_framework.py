from trytond.pool import PoolMeta, Pool
from trytond.rpc import RPC
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.model import ModelView, ModelSQL

from trytond.modules.cog_utils import coop_string, utils, fields


__all__ = [
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
            return super(DynamicButtonDict, self).__getitem__(name)
        # Remove the prefix before going forward
        button_data = name[len(self.allowed_prefix):].split('_')
        return self.for_class.calculate_button_states(button_data)

    def __contains__(self, name):
        # Names starting sith the allowed prefix are in, no matter what !
        if name.startswith(self.allowed_prefix):
            return True
        return super(DynamicButtonDict, self).__contains__(name)


class ClassAttr(PoolMeta):
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
            return self._default_button_method(name)
        return super(ClassAttr, self).__getattr__(name)


class ProcessFramework(ModelView):
    'Process Framework'

    __metaclass__ = ClassAttr
    __allowed_buttons__ = '_button_'
    __name__ = 'process.process_framework'

    # The current state is used to store which process is currently being
    # executed and which step is the current step
    current_state = fields.Many2One('process-process.step', 'Current State',
        ondelete='RESTRICT', states={'readonly': True})
    task_name = fields.Function(
        fields.Char('Task Name'),
        'get_task_name')
    task_status = fields.Function(
        fields.Char('Task Status'),
        'get_task_status', searcher='search_task_status')

    @classmethod
    def _export_light(cls):
        res = super(ProcessFramework, cls)._export_light()
        res.add('current_state')
        return res

    @classmethod
    def __setup__(cls):
        super(ProcessFramework, cls).__setup__()
        # We prepare the class to respond to generated buttons
        cls.__rpc__ = AllowRPCDict(cls.__allowed_buttons__, cls.__rpc__)
        # We also need to plug in a way to properly set the states for
        # thsoe buttons
        cls._buttons = DynamicButtonDict(cls.__allowed_buttons__,
            cls._buttons, cls)
        cls._error_messages.update({
                'everything_ok': 'Everything is good !',
                'field_required': "Enter a value for field(s): %s",
                'child_field_required': "Enter a value for field '%s' of '%s'",
                'date_in_future': 'Select a date that is not in the future '
                'for field(s): %s',
                })
        if issubclass(cls, ModelSQL):
            cls.order_task_status = cls._order_task_status

    @classmethod
    def __register__(cls, module_name):
        super(ProcessFramework, cls).__register__(module_name)
        GoodModel = Pool().get('ir.model')
        good_model, = GoodModel.search([('model', '=', cls.__name__)], limit=1)
        good_model.is_workflow = True
        good_model.save()

    @classmethod
    def build_instruction_transition_method(cls, process, transition):
        def button_transition_generic(works):
            ProcessTransition = Pool().get('process.transition')
            good_trans = ProcessTransition(int(transition[0]))
            result = None
            for work in works:
                result = good_trans.execute(work)
                work.save()
            return result
        return button_transition_generic

    @classmethod
    def _default_button_method(cls, button_name):
        def void(works):
            return
        button_data = button_name.split('_')
        if not button_data:
            return void
        # The pattern for the transition is as follow :
        #      <instruction>_<process_desc_id>(_<data>)
        instruction = button_data[0]
        Process = Pool().get('process')
        process = Process(button_data[1])
        try:
            return getattr(cls, 'build_instruction_%s_method' % instruction)(
                process, button_data[2:])
        except AttributeError:
            return void

    def set_state(self, value, process_name=None):
        if value is None:
            self.current_state = None
            return
        # We need to know the process on which we are working.
        # Either it is a parameter of the setter, or we look for it in the
        # current context
        if not process_name:
            process_name = Transaction().context.get('running_process')
        if not process_name and self.current_state:
            process_desc = self.current_state.process
        else:
            Process = Pool().get('process')
            process_desc, = Process.search([
                    ('technical_name', '=', process_name)], limit=1)
        self.current_state = process_desc.get_step_relation(value)

    @classmethod
    def default_current_state(cls):
        # When we are first accessing the record, if we are in a process, we
        # need to get a default value so that the states work properly
        process_name = Transaction().context.get('running_process')
        if not process_name:
            return
        Process = Pool().get('process')
        process_desc, = Process.search([
                ('technical_name', '=', process_name)], limit=1)
        # The good value is the name associated to the first step of the
        # current process
        return process_desc.get_first_state_relation().id

    @classmethod
    def raise_user_error(cls, errors, error_args=None, error_description='',
            error_description_args=None, raise_exception=True):
        if (error_args or error_description or error_description_args or not
                raise_exception or not isinstance(errors, (list, tuple))):
            return super(ProcessFramework, cls).raise_user_error(
                errors, error_args, error_description, error_description_args,
                raise_exception)

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
            error = cls._error_messages.get(error, error)
            language = Transaction().language
            res = Translation.get_source(
                cls.__name__, 'error', language, error)
            if not res:
                res = Translation.get_source(error, 'error', language)
            if res:
                error = res
            try:
                error = error % error_args
            except TypeError:
                pass
            result.append(error)
        # We display the resulting list of strings
        raise UserError('\n'.join(result))

    def get_task_name(self, name=None):
        if hasattr(self, 'synthesis_rec_name'):
            return self.synthesis_rec_name
        elif hasattr(self, 'get_synthesis_rec_name'):
            return self.get_synthesis_rec_name(name)
        return self.rec_name

    def get_task_status(self, name=None):
        if self.current_state and self.current_state.status:
            return self.current_state.status.rec_name

    @classmethod
    def search_task_status(cls, name, clause):
        if clause[1] in ['=', 'ilike']:
            status = clause[2]
            return [('current_state.status.name', clause[1], status)]
        elif clause[1] == 'in':
            statuses = clause[2]
            clause = ['OR']
            for status in statuses:
                clause[0].append([('current_state.status.name', '=', status)])
            return clause
        else:
            raise NotImplementedError

    @classmethod
    def _order_task_status(cls, tables):
        task_status_order = tables.get('process.status')
        if task_status_order:
            return [task_status_order[None][0].name]
        pool = Pool()
        table, _ = tables[None]
        process_target = tables.get('_process_target', cls.__table__())
        step_relation = pool.get('process-process.step').__table__()
        status_relation = pool.get('process.status').__table__()
        query_table_1 = process_target.join(step_relation, condition=(
                process_target.current_state == step_relation.id)).select(
                    process_target.id.as_('target'),
                    step_relation.status.as_('status'))
        query_table = query_table_1.join(status_relation, condition=(
                query_table_1.status == status_relation.id)).select(
                    status_relation.name.as_('status_name'),
                    query_table_1.target)
        tables['process.status'] = {
            None: (query_table,
                (query_table.target == table.id)
                )}
        return [query_table.status_name]

    def button_is_active(self, button_name):
        good_button = self._buttons[button_name]
        if good_button is None:
            return False
        if good_button == {}:
            return True
        return not(
            'readonly' in good_button and
            utils.pyson_result(good_button['readonly'], self) or
            'invisible' in good_button and
            utils.pyson_result(good_button['invisible'], self))

    def is_button_available(self, process, executable):
        if executable.__name__ == 'process.step':
            if (self.current_state and
                    self.current_state.step.id == executable.id):
                return False
            button_name = '_button_step_%s_%s_%s' % (process.id,
                self.current_state.step.id, executable.id)
        elif executable.__name__ == 'process.transition':
            button_name = '_button_transition_%s_%s' % (
                process.id, executable.id)
        return self.button_is_active(button_name)

    def check_not_null(self, *args):
        labels = []
        for field in args:
            if not getattr(self, field):
                labels.append(coop_string.translate_label(self, field))
        if labels:
            self.append_functional_error('field_required',
                ', '.join(["'%s'" % l for l in labels]))

    def check_not_future(self, *args):
        labels = []
        for field in args:
            date = getattr(self, field)
            if date and date > utils.today():
                labels.append(coop_string.translate_label(self, field))
        if labels:
            self.append_functional_error('date_in_future',
                ', '.join(["'%s'" % l for l in labels]))

    @classmethod
    def button_transition_states(cls, process, transition_data):
        transition_id = int(transition_data[0])
        TransitionDesc = Pool().get('process.transition')
        good_transition = TransitionDesc(transition_id)
        auth_pyson = good_transition.get_pyson_authorizations()
        ro_pyson = good_transition.get_pyson_readonly()
        res = '(%s) and (%s)' % (auth_pyson, ro_pyson)
        states = {}
        if res:
            states['readonly'] = utils.pyson_encode(res, True)
        return states

    @classmethod
    def button_current_states(cls, process, data):
        return {'readonly': True}

    @classmethod
    def calculate_button_states(cls, button_data):
        if not button_data:
            return {'readonly': True}
        # The pattern for the transition is as follow :
        #      <instruction>_<process_desc_id>(_<data>)
        instruction = button_data[0]
        Process = Pool().get('process')
        process = Process(button_data[1])
        try:
            return getattr(cls, 'button_%s_states' % instruction)(
                process, button_data[2:])
        except AttributeError:
            return {'readonly': True}
