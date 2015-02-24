import datetime

from trytond.wizard import Wizard, StateAction
from trytond.wizard import StateView, Button, StateTransition
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

from trytond.modules.cog_utils import utils, model, fields

__metaclass__ = PoolMeta

__all__ = [
    'ProcessLog',
    'TaskDispatcher',
    'TaskSelector',
    'LaunchTask',
    ]


class ProcessLog:
    __name__ = 'process.log'

    task_start = fields.Function(
        fields.DateTime('Task Start'),
        'on_change_with_task_start')
    is_current_user = fields.Function(
        fields.Boolean('Is current user', depends=['user']),
        'get_is_current_user')
    task_start_date = fields.Function(
        fields.Date('Task Start'),
        'on_change_with_task_start_date')
    task_nb = fields.Function(
        fields.Integer('Task Number'),
        'get_task_nb')

    @fields.depends('task')
    def on_change_with_task_start(self, name=None):
        if not (hasattr(self, 'task') and self.task):
            return None
        start_log, = self.search([
            ('from_state', '=', None),
            ('task', '=', utils.convert_to_reference(self.task))], limit=1)
        return start_log.start_time

    @fields.depends('task')
    def on_change_with_task_start_date(self, name=None):
        if not (hasattr(self, 'task') and self.task):
            return None
        start_log, = self.search([
                ('from_state', '=', None),
                ('task', '=', utils.convert_to_reference(self.task))], limit=1)
        return start_log.start_time.date()

    def get_is_current_user(self, name):
        if not Transaction().user:
            return False
        return Transaction().user == self.user.id

    def get_task_nb(self, name):
        # used by graph presenter
        return 1


class TaskSelector(model.CoopView):
    'Task Selector'

    __name__ = 'task.select.available_tasks'

    user = fields.Many2One('res.user', 'User')
    selected_task = fields.Many2One('process.log', 'Selected Task',
        states={'readonly': True})
    selected_task_presenter = fields.Function(
        fields.One2Many('process.log', None, 'Seleteted Task', readonly=True,
            depends=['selected_task'], size=1),
        'on_change_with_selected_task_presenter')

    @fields.depends('selected_task')
    def on_change_with_selected_task_presenter(self, name=None):
        if self.selected_task:
            return [self.selected_task.id]
        return []


class TaskDispatcher(Wizard):
    'Task Dispatcher'

    __name__ = 'task.select'

    start_state = 'remove_locks'

    class VoidStateAction(StateAction):
        def __init__(self):
            StateAction.__init__(self, None)

        def get_action(self):
            return None

    remove_locks = StateTransition()
    select_context = StateView('task.select.available_tasks',
        'task_manager.task_selector_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Compute Task', 'calculate_action', 'tryton-ok'),
            ])
    calculate_action = VoidStateAction()

    @classmethod
    def __setup__(cls):
        super(TaskDispatcher, cls).__setup__()
        cls._error_messages.update({
                'no_task_selected': 'No task has been selected.',
                'no_task_found': 'No task found'
                })

    def default_select_context(self, name):
        Selector = Pool().get('task.select.available_tasks')
        User = Pool().get('res.user')
        user = User(Transaction().user)
        selector = Selector()
        selector.user = user
        task = user.search_next_priority_task()
        if not task:
            self.raise_user_error('no_task_found')
        return {'user': user.id, 'selected_task': task.id}

    def transition_remove_locks(self):
        Log = Pool().get('process.log')
        locked = Log.search([
            ('locked', '=', True),
            ('user', '=', Transaction().user)])
        if locked:
            Log.write(locked, {'locked': False})
        return 'select_context'

    def do_calculate_action(self, action):
        Log = Pool().get('process.log')
        if self.select_context.selected_task:
            good_task = self.select_context.selected_task
            good_id = good_task.task.id
            good_model = good_task.task.__name__
            act = good_task.to_state.process.get_act_window()
        else:
            self.raise_user_error('no_task_selected')

        Action = Pool().get('ir.action')
        act = Action.get_action_values(act.__name__, [act.id])[0]

        Session = Pool().get('ir.session')
        good_session, = Session.search(
            [('create_uid', '=', Transaction().user)])
        GoodModel = Pool().get(good_model)
        good_object = GoodModel(good_id)
        new_log = Log()
        new_log.user = Transaction().user
        new_log.locked = True
        new_log.task = good_object
        new_log.from_state = good_object.current_state.id
        new_log.to_state = good_object.current_state.id
        new_log.start_time = datetime.datetime.now()
        new_log.session = good_session.key
        new_log.save()

        views = act['views']
        if len(views) > 1:
            for view in views:
                if view[1] == 'form':
                    act['views'] = [view]
                    break
        res = (act, {
                'id': good_id,
                'model': good_model,
                'res_id': good_id,
                'res_model': good_model,
                })
        return res


class LaunchTask(Wizard):
    'Launch Selected Task'

    __name__ = 'task.launch'

    start_state = 'find_action'
    find_action = StateTransition()
    view_task = model.VoidStateAction()
    resume_process_action = StateAction('process_cog.act_resume_process')

    @property
    def current_log(self):
        active_id = Transaction().context.get('active_id')
        active_model = Transaction().context.get('active_model')
        assert active_model == 'process.log'
        return Pool().get('process.log')(active_id)

    def transition_find_action(self):
        if self.current_log.user.id in (Transaction().user, 0, 1):
            # Users 0 is root (technical) and user 1 is admin. Those should not
            # interfere with the process
            return 'resume_process_action'
        return 'view_task'

    def do_view_task(self, action):
        pool = Pool()
        log = self.current_log
        Action = pool.get('ir.action')
        ActWindow = pool.get('ir.action.act_window')
        possible_actions = ActWindow.search([
                ('res_model', '=', log.task.__name__)])
        good_action = possible_actions[0]
        action = Action.get_action_values(
            'ir.action.act_window', [good_action.id])[0]

        views = action['views']
        if len(views) > 1:
            for view in views:
                if view[1] == 'form':
                    action['views'] = [view]
                    break
        return (action, {
                'id': log.task.id,
                'model': log.task.__name__,
                'res_id': log.task.id,
                'res_model': log.task.__name__,
                })

    def do_resume_process_action(self, action):
        log = self.current_log

        return (action, {
                'id': log.task.id,
                'model': log.task.__name__,
                'res_id': log.task.id,
                'res_model': log.task.__name__,
                })
